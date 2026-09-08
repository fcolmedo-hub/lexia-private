from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any, Iterable


RELATIONS = {
    "duplicate_of",
    "specializes",
    "generalizes",
    "exception_to",
    "related_to",
    "supports",
    "contradicts",
}
DIRECTIONS = {"a_to_b", "b_to_a", "symmetric", "not_applicable"}
CONFIDENCES = {"high", "medium", "low"}


DECISIONS_SCHEMA = """
CREATE TABLE IF NOT EXISTS relation_decisions (
    candidate_id TEXT PRIMARY KEY,
    a_standard_uid TEXT NOT NULL REFERENCES standards(standard_uid) ON DELETE CASCADE,
    b_standard_uid TEXT NOT NULL REFERENCES standards(standard_uid) ON DELETE CASCADE,
    relation_type TEXT NOT NULL CHECK(relation_type IN ('none','duplicate_of','specializes','generalizes','exception_to','related_to','supports','contradicts')),
    direction TEXT NOT NULL CHECK(direction IN ('a_to_b','b_to_a','symmetric','not_applicable')),
    confidence TEXT CHECK(confidence IS NULL OR confidence IN ('high','medium','low')),
    rationale TEXT,
    decision_status TEXT NOT NULL DEFAULT 'automated' CHECK(decision_status IN ('automated','reviewed')),
    relation_id INTEGER REFERENCES relations(relation_id) ON DELETE SET NULL,
    classifier_model TEXT,
    source_file TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_relation_decisions_pair
    ON relation_decisions(a_standard_uid, b_standard_uid);
CREATE INDEX IF NOT EXISTS idx_relation_decisions_relation
    ON relation_decisions(relation_type, decision_status);
"""


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as fh:
        for lineno, raw in enumerate(fh, 1):
            if not raw.strip():
                continue
            value = json.loads(raw)
            if not isinstance(value, dict):
                raise RuntimeError(f"Registro no-objeto en {path}, línea {lineno}")
            rows.append(value)
    return rows


def load_audit_overrides(paths: Iterable[Path]) -> tuple[dict[str, dict[str, Any]], list[str]]:
    overrides: dict[str, dict[str, Any]] = {}
    used: list[str] = []
    for path in paths:
        if not path.exists():
            continue
        used.append(str(path.resolve()))
        for row in load_jsonl(path):
            if row.get("audit_status") != "reviewed":
                continue
            candidate_id = str(row.get("candidate_id") or "").strip()
            relation = str(row.get("audited_relation") or "").strip()
            direction = str(row.get("audited_direction") or "").strip()
            if not candidate_id or not relation or not direction:
                raise RuntimeError(f"Auditoría revisada incompleta en {path}")
            overrides[candidate_id] = {
                "relation": relation,
                "direction": direction,
                "rationale": row.get("audit_comment") or row.get("rationale"),
            }
    return overrides, used


def resolve_endpoints(a_uid: str, b_uid: str, direction: str) -> tuple[str, str]:
    if direction == "a_to_b":
        return a_uid, b_uid
    if direction == "b_to_a":
        return b_uid, a_uid
    if direction == "symmetric":
        return tuple(sorted((a_uid, b_uid)))  # type: ignore[return-value]
    raise ValueError(f"Dirección inválida para relación positiva: {direction!r}")


def _table_exists(conn: sqlite3.Connection, name: str) -> bool:
    return conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)
    ).fetchone() is not None


def _normalize_rows(
    rows: Iterable[dict[str, Any]], overrides: dict[str, dict[str, Any]]
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    normalized: list[dict[str, Any]] = []
    stats = {"invalid": 0, "overrides_applied": 0}
    for row in rows:
        if row.get("valid") is False:
            stats["invalid"] += 1
            continue
        candidate_id = str(row.get("candidate_id") or row.get("custom_id") or "").strip()
        a_uid = str(row.get("a_uid") or "").strip()
        b_uid = str(row.get("b_uid") or "").strip()
        relation = str(row.get("relation") or "").strip()
        direction = str(row.get("direction") or "").strip()
        rationale = str(row.get("rationale") or "").strip()
        decision_status = "automated"

        override = overrides.get(candidate_id)
        if override:
            relation = str(override["relation"])
            direction = str(override["direction"])
            if override.get("rationale"):
                rationale = str(override["rationale"])
            decision_status = "reviewed"
            stats["overrides_applied"] += 1

        confidence = str(row.get("confidence") or "").strip() or None
        valid_relation = relation == "none" or relation in RELATIONS
        valid_direction = direction in DIRECTIONS
        direction_matches = (relation == "none" and direction == "not_applicable") or (
            relation in RELATIONS and direction != "not_applicable"
        )
        if (
            not candidate_id
            or not a_uid
            or not b_uid
            or a_uid == b_uid
            or not valid_relation
            or not valid_direction
            or not direction_matches
            or (confidence is not None and confidence not in CONFIDENCES)
        ):
            stats["invalid"] += 1
            continue

        normalized.append({
            "candidate_id": candidate_id,
            "a_uid": a_uid,
            "b_uid": b_uid,
            "relation": relation,
            "direction": direction,
            "confidence": confidence,
            "rationale": rationale,
            "decision_status": decision_status,
        })

    # Un candidate_id representa un único par. Una repetición idéntica es inocua;
    # ante versiones distintas gana la decisión revisada y luego la última.
    deduped: dict[str, dict[str, Any]] = {}
    for item in normalized:
        current = deduped.get(item["candidate_id"])
        if current is None or item["decision_status"] == "reviewed" or current["decision_status"] != "reviewed":
            deduped[item["candidate_id"]] = item
    return list(deduped.values()), stats


def apply_relation_decisions(
    db_path: Path,
    classifications: Iterable[dict[str, Any]],
    *,
    audit_paths: Iterable[Path] = (),
    classifier_model: str | None = None,
    source_file: str | None = None,
    apply: bool = False,
) -> dict[str, Any]:
    overrides, audit_files = load_audit_overrides(audit_paths)
    rows = list(classifications)
    decisions, normalization = _normalize_rows(rows, overrides)

    conn = sqlite3.connect(db_path)
    try:
        conn.execute("PRAGMA foreign_keys=ON")
        standard_uids = {str(r[0]) for r in conn.execute("SELECT standard_uid FROM standards")}
        decisions_table_exists = _table_exists(conn, "relation_decisions")
        ready = [d for d in decisions if d["a_uid"] in standard_uids and d["b_uid"] in standard_uids]
        missing = [d for d in decisions if d["a_uid"] not in standard_uids or d["b_uid"] not in standard_uids]
        already_decided = 0
        if decisions_table_exists and ready:
            known_ids = {str(row[0]) for row in conn.execute("SELECT candidate_id FROM relation_decisions")}
            already_decided = len(known_ids.intersection(d["candidate_id"] for d in ready))

        result: dict[str, Any] = {
            "mode": "apply" if apply else "dry_run",
            "classifications": len(rows),
            "valid_decisions": len(decisions),
            "invalid": normalization["invalid"],
            "audit_overrides_loaded": len(overrides),
            "audit_files_used": audit_files,
            "overrides_applied": normalization["overrides_applied"],
            "ready_for_sqlite": len(ready),
            "missing_standard": len(missing),
            "already_decided": already_decided,
            "none_decisions": sum(d["relation"] == "none" for d in ready),
            "positive_decisions": sum(d["relation"] != "none" for d in ready),
            "relation_counts": {},
        }
        counts: dict[str, int] = {}
        for item in ready:
            counts[item["relation"]] = counts.get(item["relation"], 0) + 1
        result["relation_counts"] = dict(sorted(counts.items()))
        if missing:
            result["missing_examples"] = [d["candidate_id"] for d in missing[:10]]

        if not apply:
            return result

        inserted_or_updated = 0
        removed_obsolete_proposed = 0
        preserved_terminal = 0
        with conn:
            conn.executescript(DECISIONS_SCHEMA)
            for item in ready:
                previous = conn.execute(
                    """SELECT relation_id,relation_type,direction,confidence,rationale,decision_status
                       FROM relation_decisions WHERE candidate_id=?""",
                    (item["candidate_id"],),
                ).fetchone()
                relation_id: int | None = None
                if previous and previous[0] is not None:
                    previous_relation = conn.execute(
                        "SELECT status FROM relations WHERE relation_id=?", (previous[0],)
                    ).fetchone()
                    if previous_relation and str(previous_relation[0]) in {"confirmed", "rejected"}:
                        preserved_terminal += 1
                        continue
                    same_decision = (
                        str(previous[1]) == item["relation"]
                        and str(previous[2]) == item["direction"]
                    )
                    if previous_relation and same_decision:
                        relation_id = int(previous[0])
                    elif previous_relation:
                        conn.execute("DELETE FROM relations WHERE relation_id=?", (previous[0],))
                        removed_obsolete_proposed += 1

                if item["relation"] != "none" and relation_id is None:
                    from_uid, to_uid = resolve_endpoints(
                        item["a_uid"], item["b_uid"], item["direction"]
                    )
                    existing = conn.execute(
                        """SELECT relation_id,status FROM relations
                           WHERE from_standard_uid=? AND to_standard_uid=? AND relation_type=?""",
                        (from_uid, to_uid, item["relation"]),
                    ).fetchone()
                    if existing and str(existing[1]) in {"confirmed", "rejected"}:
                        relation_id = int(existing[0])
                        preserved_terminal += 1
                    else:
                        conn.execute(
                            """INSERT INTO relations(from_standard_uid,to_standard_uid,relation_type,status,rationale)
                               VALUES(?,?,?,?,?)
                               ON CONFLICT(from_standard_uid,to_standard_uid,relation_type)
                               DO UPDATE SET rationale=excluded.rationale""",
                            (from_uid, to_uid, item["relation"], "proposed", item["rationale"]),
                        )
                        relation_id = int(conn.execute(
                            """SELECT relation_id FROM relations
                               WHERE from_standard_uid=? AND to_standard_uid=? AND relation_type=?""",
                            (from_uid, to_uid, item["relation"]),
                        ).fetchone()[0])

                conn.execute(
                    """INSERT INTO relation_decisions(
                           candidate_id,a_standard_uid,b_standard_uid,relation_type,direction,
                           confidence,rationale,decision_status,relation_id,classifier_model,source_file
                       ) VALUES(?,?,?,?,?,?,?,?,?,?,?)
                       ON CONFLICT(candidate_id) DO UPDATE SET
                           a_standard_uid=excluded.a_standard_uid,
                           b_standard_uid=excluded.b_standard_uid,
                           relation_type=excluded.relation_type,
                           direction=excluded.direction,
                           confidence=excluded.confidence,
                           rationale=excluded.rationale,
                           decision_status=excluded.decision_status,
                           relation_id=excluded.relation_id,
                           classifier_model=excluded.classifier_model,
                           source_file=excluded.source_file,
                           updated_at=CURRENT_TIMESTAMP""",
                    (
                        item["candidate_id"], item["a_uid"], item["b_uid"], item["relation"],
                        item["direction"], item["confidence"], item["rationale"],
                        item["decision_status"], relation_id, classifier_model, source_file,
                    ),
                )
                inserted_or_updated += 1

        result.update({
            "sqlite_decisions_inserted_or_updated": inserted_or_updated,
            "sqlite_obsolete_proposed_removed": removed_obsolete_proposed,
            "sqlite_preserved_confirmed_or_rejected": preserved_terminal,
            "sqlite_decisions_total": conn.execute("SELECT COUNT(*) FROM relation_decisions").fetchone()[0],
            "sqlite_relations_total": conn.execute("SELECT COUNT(*) FROM relations").fetchone()[0],
        })
        return result
    finally:
        conn.close()
