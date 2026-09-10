from __future__ import annotations

import hashlib
import json
import re
import sqlite3
import unicodedata
from collections import defaultdict
from dataclasses import dataclass
from typing import Any


CANONICAL_SCHEMA_STATEMENTS = (
"""CREATE TABLE IF NOT EXISTS canonical_standards (
    canonical_uid TEXT PRIMARY KEY,
    statement TEXT NOT NULL,
    representative_standard_uid TEXT NOT NULL REFERENCES standards(standard_uid) ON DELETE RESTRICT,
    status TEXT NOT NULL DEFAULT 'confirmed' CHECK(status IN ('proposed','confirmed','rejected')),
    statement_source TEXT NOT NULL DEFAULT 'occurrence' CHECK(statement_source IN ('occurrence','manual')),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);""",
"""CREATE INDEX IF NOT EXISTS idx_canonical_representative
    ON canonical_standards(representative_standard_uid);""",

"""CREATE TABLE IF NOT EXISTS standard_occurrences (
    standard_uid TEXT PRIMARY KEY REFERENCES standards(standard_uid) ON DELETE CASCADE,
    canonical_uid TEXT NOT NULL REFERENCES canonical_standards(canonical_uid) ON DELETE CASCADE,
    membership_status TEXT NOT NULL DEFAULT 'confirmed' CHECK(membership_status IN ('proposed','confirmed','rejected')),
    match_basis TEXT NOT NULL CHECK(match_basis IN ('singleton','exact_text','confirmed_duplicate','reviewed_duplicate','manual')),
    confidence TEXT CHECK(confidence IS NULL OR confidence IN ('high','medium','low')),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);""",
"""CREATE INDEX IF NOT EXISTS idx_occurrences_canonical
    ON standard_occurrences(canonical_uid);""",

"""CREATE VIRTUAL TABLE IF NOT EXISTS canonical_standards_fts USING fts5(
    canonical_uid UNINDEXED,
    statement,
    variants,
    conditions,
    consequence,
    exceptions,
    tokenize='unicode61 remove_diacritics 2'
);""",
)


def _table_exists(conn: sqlite3.Connection, name: str) -> bool:
    return conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type IN ('table','view') AND name=?",
        (name,),
    ).fetchone() is not None


def ensure_canonical_schema(conn: sqlite3.Connection) -> None:
    for statement in CANONICAL_SCHEMA_STATEMENTS:
        conn.execute(statement)


def normalize_exact_statement(value: Any) -> str:
    """Normalize only typographic differences; semantic equality stays reviewed."""
    text = unicodedata.normalize("NFKD", str(value or "").casefold())
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = re.sub(r"[^\w]+", " ", text, flags=re.UNICODE)
    return re.sub(r"\s+", " ", text).strip()


class _UnionFind:
    def __init__(self, values: list[str]) -> None:
        self.parent = {value: value for value in values}

    def find(self, value: str) -> str:
        parent = self.parent[value]
        if parent != value:
            self.parent[value] = self.find(parent)
        return self.parent[value]

    def union(self, left: str, right: str) -> None:
        a = self.find(left)
        b = self.find(right)
        if a != b:
            self.parent[max(a, b)] = min(a, b)


@dataclass(frozen=True)
class DuplicateEdge:
    left: str
    right: str
    basis: str
    confidence: str | None


def _duplicate_edges(conn: sqlite3.Connection) -> tuple[list[DuplicateEdge], int]:
    if not _table_exists(conn, "relations"):
        return [], 0
    has_decisions = _table_exists(conn, "relation_decisions")
    decision_select = (
        """EXISTS(
               SELECT 1 FROM relation_decisions rd
               WHERE rd.relation_id=r.relation_id
                 AND rd.relation_type='duplicate_of'
                 AND rd.decision_status='reviewed'
           ) AS reviewed,
           (SELECT rd.confidence FROM relation_decisions rd
            WHERE rd.relation_id=r.relation_id
              AND rd.relation_type='duplicate_of'
            ORDER BY CASE rd.decision_status WHEN 'reviewed' THEN 0 ELSE 1 END
            LIMIT 1) AS confidence"""
        if has_decisions
        else "0 AS reviewed, NULL AS confidence"
    )
    rows = conn.execute(
        f"""SELECT r.from_standard_uid,r.to_standard_uid,r.status,
                    {decision_select}
             FROM relations r
             WHERE r.relation_type='duplicate_of' AND r.status<>'rejected'"""
    ).fetchall()
    accepted: list[DuplicateEdge] = []
    proposed = 0
    for row in rows:
        left, right, status, reviewed, confidence = row
        if str(status) == "confirmed":
            accepted.append(DuplicateEdge(str(left), str(right), "confirmed_duplicate", confidence))
        elif bool(reviewed):
            accepted.append(DuplicateEdge(str(left), str(right), "reviewed_duplicate", confidence))
        else:
            proposed += 1
    return accepted, proposed


def _representative_key(row: sqlite3.Row) -> tuple[Any, ...]:
    return (
        0 if str(row["review_status"]) == "validated" else 1,
        {"published": 0, "ready": 1, "blocked": 2, "hidden": 3}.get(
            str(row["publication_status"]), 4
        ),
        0 if str(row["treatment"]) == "adopta" else 1,
        0 if str(row["speaker"]) == "mayoria" else 1,
        str(row["created_at"] or ""),
        str(row["standard_uid"]),
    )


def _canonical_uid(rows: list[sqlite3.Row]) -> str:
    oldest = min(rows, key=lambda row: (str(row["created_at"] or ""), str(row["standard_uid"])))
    digest = hashlib.sha256(str(oldest["standard_uid"]).encode("utf-8")).hexdigest()
    return "CAN-" + digest[:24]


def _json_list(value: Any) -> list[Any]:
    try:
        parsed = json.loads(str(value or "[]"))
        return parsed if isinstance(parsed, list) else []
    except Exception:
        return []


def rebuild_canonical_groups(conn: sqlite3.Connection) -> dict[str, int]:
    """Materialize confirmed canonical groups without rewriting any occurrence.

    Exact typographic equality is safe to consolidate automatically. Semantic
    paraphrases are consolidated only after a confirmed `duplicate_of` relation
    or a reviewed classifier decision. Automated proposed duplicates remain
    separate suggestions for the product UI.
    """
    conn.row_factory = sqlite3.Row
    ensure_canonical_schema(conn)
    rows = conn.execute(
        """SELECT standard_uid,local_identifier,statement,speaker,treatment,conditions_json,
                  consequence,exceptions_json,review_status,publication_status,
                  created_at
           FROM standards
           WHERE review_status<>'rejected'
           ORDER BY created_at,standard_uid"""
    ).fetchall()
    uids = [str(row["standard_uid"]) for row in rows]
    by_uid = {str(row["standard_uid"]): row for row in rows}
    union = _UnionFind(uids)

    exact: dict[str, list[str]] = defaultdict(list)
    for row in rows:
        signature = normalize_exact_statement(row["statement"])
        if signature:
            exact[signature].append(str(row["standard_uid"]))
    exact_groups = 0
    exact_members: set[str] = set()
    for members in exact.values():
        if len(members) < 2:
            continue
        exact_groups += 1
        exact_members.update(members)
        for uid in members[1:]:
            union.union(members[0], uid)

    edges, proposed_suggestions = _duplicate_edges(conn)
    relation_basis: dict[str, tuple[str, str | None]] = {}
    accepted_edges = 0
    for edge in edges:
        if edge.left not in by_uid or edge.right not in by_uid:
            continue
        union.union(edge.left, edge.right)
        accepted_edges += 1
        for uid in (edge.left, edge.right):
            current = relation_basis.get(uid)
            if current is None or edge.basis == "reviewed_duplicate":
                relation_basis[uid] = (edge.basis, edge.confidence)

    components: dict[str, list[sqlite3.Row]] = defaultdict(list)
    for row in rows:
        components[union.find(str(row["standard_uid"]))].append(row)

    previous = {
        str(row["canonical_uid"]): dict(row)
        for row in conn.execute("SELECT * FROM canonical_standards")
    }
    conn.execute("DELETE FROM standard_occurrences")
    conn.execute("DELETE FROM canonical_standards_fts")

    used: set[str] = set()
    multi_occurrence = 0
    multi_document = 0
    for component_rows in components.values():
        canonical_uid = _canonical_uid(component_rows)
        used.add(canonical_uid)
        representative = min(component_rows, key=_representative_key)
        old = previous.get(canonical_uid)
        statement_source = str(old.get("statement_source")) if old else "occurrence"
        statement = (
            str(old.get("statement"))
            if old and statement_source == "manual"
            else str(representative["statement"])
        )
        conn.execute(
            """INSERT INTO canonical_standards(
                   canonical_uid,statement,representative_standard_uid,status,statement_source
               ) VALUES(?,?,?,?,?)
               ON CONFLICT(canonical_uid) DO UPDATE SET
                   statement=excluded.statement,
                   representative_standard_uid=excluded.representative_standard_uid,
                   status=excluded.status,
                   statement_source=excluded.statement_source,
                   updated_at=CURRENT_TIMESTAMP""",
            (canonical_uid, statement, representative["standard_uid"], "confirmed", statement_source),
        )

        if len(component_rows) > 1:
            multi_occurrence += 1
        document_count = conn.execute(
            "SELECT COUNT(DISTINCT document_id) FROM standards WHERE standard_uid IN (%s)"
            % ",".join("?" for _ in component_rows),
            [row["standard_uid"] for row in component_rows],
        ).fetchone()[0]
        if int(document_count) > 1:
            multi_document += 1

        variants: list[str] = []
        conditions: list[str] = []
        consequences: list[str] = []
        exceptions: list[str] = []
        for row in component_rows:
            uid = str(row["standard_uid"])
            if uid in relation_basis:
                basis, confidence = relation_basis[uid]
            elif uid in exact_members:
                basis, confidence = "exact_text", "high"
            elif str(row["local_identifier"] if "local_identifier" in row.keys() else "") == "MANUAL":
                basis, confidence = "manual", None
            else:
                basis, confidence = "singleton", None
            conn.execute(
                """INSERT INTO standard_occurrences(
                       standard_uid,canonical_uid,membership_status,match_basis,confidence
                   ) VALUES(?,?,?,?,?)""",
                (uid, canonical_uid, "confirmed", basis, confidence),
            )
            wording = str(row["statement"])
            if normalize_exact_statement(wording) != normalize_exact_statement(statement):
                variants.append(wording)
            conditions.extend(str(value) for value in _json_list(row["conditions_json"]) if value)
            if row["consequence"]:
                consequences.append(str(row["consequence"]))
            exceptions.extend(str(value) for value in _json_list(row["exceptions_json"]) if value)

        conn.execute(
            """INSERT INTO canonical_standards_fts(
                   canonical_uid,statement,variants,conditions,consequence,exceptions
               ) VALUES(?,?,?,?,?,?)""",
            (
                canonical_uid,
                statement,
                " | ".join(dict.fromkeys(variants)),
                " | ".join(dict.fromkeys(conditions)),
                " | ".join(dict.fromkeys(consequences)),
                " | ".join(dict.fromkeys(exceptions)),
            ),
        )

    obsolete = set(previous) - used
    for canonical_uid in obsolete:
        conn.execute("DELETE FROM canonical_standards WHERE canonical_uid=?", (canonical_uid,))

    return {
        "standards": len(rows),
        "canonical_standards": len(components),
        "occurrences": len(rows),
        "multi_occurrence_groups": multi_occurrence,
        "multi_document_groups": multi_document,
        "exact_groups": exact_groups,
        "accepted_duplicate_edges": accepted_edges,
        "proposed_duplicate_suggestions": proposed_suggestions,
    }
