from __future__ import annotations

import json
import re
import sqlite3
from pathlib import Path
from typing import Any

from config.settings import SETTINGS


WEAK_PROPOSED_RELATIONS = {"related_to", "supports"}
STRONG_RELATIONS = {"duplicate_of", "specializes", "generalizes", "exception_to", "contradicts"}


def _fts_query(value: str) -> str:
    """Turn free-form legal text into a safe, recall-oriented FTS5 query."""
    tokens: list[str] = []
    seen: set[str] = set()
    for token in re.findall(r"[^\W_]+", str(value or ""), flags=re.UNICODE):
        key = token.casefold()
        if key in seen:
            continue
        seen.add(key)
        tokens.append(token.replace('"', '""'))
    return " OR ".join(f'"{token}"' for token in tokens)


def _ro_connect(path: Path) -> sqlite3.Connection:
    uri = path.resolve().as_uri() + "?mode=ro"
    con = sqlite3.connect(uri, uri=True, timeout=3)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA query_only=ON")
    return con


def _loads(value: Any, fallback):
    try:
        parsed = json.loads(str(value or ""))
        return parsed
    except Exception:
        return fallback


class StandardsService:
    """Read-only product service for LexIA legal standards.

    Publication policy:
    - rejected/hidden/blocked standards are never exposed.
    - validated standards in ready/published are searchable.
    - confirmed relations are always exposed.
    - proposed weak relations (related_to/supports) may be exposed with a badge.
    - proposed strong relations stay hidden until confirmed.
    """

    def __init__(self, db_path: Path | None = None) -> None:
        self.db_path = Path(db_path or (SETTINGS.runtime_path / "standards" / "standards.sqlite3"))

    def available(self) -> bool:
        return self.db_path.exists()

    def _base_visibility_sql(self) -> str:
        return "s.review_status='validated' AND s.publication_status IN ('ready','published')"

    def count(self) -> int:
        """Return the standards exposed by the dictionary, never fragment counts."""
        if not self.available():
            return 0
        with _ro_connect(self.db_path) as con:
            return int(con.execute(
                "SELECT COUNT(*) FROM standards s WHERE " + self._base_visibility_sql()
            ).fetchone()[0])

    def search(
        self,
        *,
        text: str = "",
        tags: list[str] | None = None,
        court: str = "",
        date_from: str = "",
        date_to: str = "",
        speaker: str = "",
        treatment: str = "",
        limit: int = 50,
        offset: int = 0,
    ) -> dict[str, Any]:
        if not self.available():
            return {"ok": True, "available": False, "total": 0, "items": [], "filters": {}}

        tags = [str(x).strip() for x in (tags or []) if str(x).strip()]
        text = str(text or "").strip()
        where = [self._base_visibility_sql()]
        params: list[Any] = []
        joins = ["JOIN documents d ON d.document_id=s.document_id"]
        score_sql = "0.0 AS rank"

        if text:
            fts_query = _fts_query(text)
            if fts_query:
                joins.append("JOIN standards_fts f ON f.standard_uid=s.standard_uid")
                where.append("f.standards_fts MATCH ?")
                params.append(fts_query)
                score_sql = "bm25(standards_fts) AS rank"
            else:
                where.append("0")
        if court:
            where.append("LOWER(COALESCE(d.court,'')) LIKE LOWER(?)")
            params.append(f"%{court.strip()}%")
        if date_from:
            where.append("COALESCE(d.judgment_date,'') >= ?")
            params.append(date_from.strip())
        if date_to:
            where.append("COALESCE(d.judgment_date,'') <= ?")
            params.append(date_to.strip())
        if speaker:
            where.append("s.speaker=?")
            params.append(speaker.strip())
        if treatment:
            where.append("s.treatment=?")
            params.append(treatment.strip())
        if tags:
            placeholders = ",".join("?" for _ in tags)
            where.append(
                f"s.standard_uid IN (SELECT st.standard_uid FROM standard_tags st JOIN tags t ON t.tag_id=st.tag_id WHERE t.name IN ({placeholders}) GROUP BY st.standard_uid HAVING COUNT(DISTINCT t.name)=?)"
            )
            params.extend(tags)
            params.append(len(set(tags)))

        from_sql = " FROM standards s " + " ".join(joins)
        where_sql = " WHERE " + " AND ".join(where)
        order_sql = " ORDER BY rank ASC, d.judgment_date DESC, s.standard_uid" if text else " ORDER BY d.judgment_date DESC, s.standard_uid"

        with _ro_connect(self.db_path) as con:
            total = int(con.execute("SELECT COUNT(*)" + from_sql + where_sql, params).fetchone()[0])
            rows = con.execute(
                "SELECT s.standard_uid,s.statement,s.speaker,s.source_speaker,s.treatment,s.review_status,s.publication_status,d.document_name,d.document_path,d.court,d.judgment_date," + score_sql + from_sql + where_sql + order_sql + " LIMIT ? OFFSET ?",
                [*params, max(1, min(int(limit), 200)), max(0, int(offset))],
            ).fetchall()
            items = [dict(r) for r in rows]
            filters = self.filter_values(con)
        return {"ok": True, "available": True, "total": total, "items": items, "filters": filters}

    def filter_values(self, con: sqlite3.Connection | None = None) -> dict[str, list[str]]:
        owns = con is None
        if owns:
            if not self.available():
                return {"courts": [], "speakers": [], "treatments": [], "tags": []}
            con = _ro_connect(self.db_path)
        assert con is not None
        try:
            return {
                "courts": [str(r[0]) for r in con.execute("SELECT DISTINCT court FROM documents WHERE court IS NOT NULL AND TRIM(court)<>'' ORDER BY court")],
                "speakers": [str(r[0]) for r in con.execute("SELECT DISTINCT speaker FROM standards WHERE review_status='validated' ORDER BY speaker")],
                "treatments": [str(r[0]) for r in con.execute("SELECT DISTINCT treatment FROM standards WHERE review_status='validated' ORDER BY treatment")],
                "tags": [str(r[0]) for r in con.execute("SELECT name FROM tags ORDER BY name")],
            }
        finally:
            if owns:
                con.close()

    def get_standard(self, standard_uid: str, *, include_proposed_weak: bool = True) -> dict[str, Any] | None:
        if not self.available():
            return None
        uid = str(standard_uid or "").strip()
        if not uid:
            return None
        with _ro_connect(self.db_path) as con:
            row = con.execute(
                """SELECT s.*,d.document_name,d.document_path,d.source_key,d.court,d.judgment_date,d.metadata_json
                   FROM standards s JOIN documents d ON d.document_id=s.document_id
                   WHERE s.standard_uid=? AND """ + self._base_visibility_sql(),
                (uid,),
            ).fetchone()
            if row is None:
                return None
            item = dict(row)
            item["conditions"] = _loads(item.pop("conditions_json", "[]"), [])
            item["exceptions"] = _loads(item.pop("exceptions_json", "[]"), [])
            item["metadata"] = _loads(item.pop("metadata_json", "{}"), {})
            item["quotes"] = [dict(r) for r in con.execute(
                "SELECT evidence_index,chunk_id,page_start,page_end,unit_ids_json,quote_text,validation FROM quotes WHERE standard_uid=? ORDER BY evidence_index",
                (uid,),
            )]
            for quote in item["quotes"]:
                quote["unit_ids"] = _loads(quote.pop("unit_ids_json", "[]"), [])
            item["tags"] = [str(r[0]) for r in con.execute(
                "SELECT t.name FROM tags t JOIN standard_tags st ON st.tag_id=t.tag_id WHERE st.standard_uid=? ORDER BY t.name",
                (uid,),
            )]
            item["relations"] = self._relations_for(con, uid, include_proposed_weak=include_proposed_weak)
            return item

    def _relations_for(self, con: sqlite3.Connection, uid: str, *, include_proposed_weak: bool) -> list[dict[str, Any]]:
        rows = con.execute(
            """SELECT r.relation_id,r.from_standard_uid,r.to_standard_uid,r.relation_type,r.status,r.rationale,
                      CASE WHEN r.from_standard_uid=? THEN r.to_standard_uid ELSE r.from_standard_uid END other_uid
               FROM relations r
               WHERE (r.from_standard_uid=? OR r.to_standard_uid=?) AND r.status<>'rejected'""",
            (uid, uid, uid),
        ).fetchall()
        out: list[dict[str, Any]] = []
        for r in rows:
            relation_type = str(r["relation_type"])
            status = str(r["status"])
            if status != "confirmed":
                if not include_proposed_weak or relation_type not in WEAK_PROPOSED_RELATIONS:
                    continue
            other = con.execute(
                "SELECT s.standard_uid,s.statement,s.speaker,s.treatment,d.document_name,d.court,d.judgment_date FROM standards s JOIN documents d ON d.document_id=s.document_id WHERE s.standard_uid=? AND " + self._base_visibility_sql(),
                (r["other_uid"],),
            ).fetchone()
            if other is None:
                continue
            direction = "out" if str(r["from_standard_uid"]) == uid else "in"
            out.append({
                "relation_id": r["relation_id"],
                "relation_type": relation_type,
                "status": status,
                "direction": direction,
                "rationale": r["rationale"],
                "other": dict(other),
                "requires_confirmation": status == "proposed" and relation_type in STRONG_RELATIONS,
            })
        return out

    def graph(self, standard_uid: str, *, depth: int = 1, include_proposed_weak: bool = True) -> dict[str, Any]:
        root = self.get_standard(standard_uid, include_proposed_weak=include_proposed_weak)
        if root is None:
            return {"ok": False, "error": "standard_not_found", "nodes": [], "edges": []}
        max_depth = max(1, min(int(depth), 3))
        nodes: dict[str, dict[str, Any]] = {root["standard_uid"]: {k: root.get(k) for k in ("standard_uid", "statement", "speaker", "treatment", "document_name", "court", "judgment_date")}}
        edges: dict[int, dict[str, Any]] = {}
        frontier = {root["standard_uid"]}
        visited = set()
        for _ in range(max_depth):
            next_frontier = set()
            for uid in frontier - visited:
                detail = self.get_standard(uid, include_proposed_weak=include_proposed_weak)
                if not detail:
                    continue
                visited.add(uid)
                for rel in detail["relations"]:
                    other = rel["other"]
                    nodes[other["standard_uid"]] = other
                    edges[int(rel["relation_id"])] = {
                        "relation_id": rel["relation_id"],
                        "from": uid if rel["direction"] == "out" else other["standard_uid"],
                        "to": other["standard_uid"] if rel["direction"] == "out" else uid,
                        "relation_type": rel["relation_type"],
                        "status": rel["status"],
                        "rationale": rel["rationale"],
                    }
                    next_frontier.add(other["standard_uid"])
            frontier = next_frontier
        return {"ok": True, "root": standard_uid, "nodes": list(nodes.values()), "edges": list(edges.values())}

    def investigation_sources(self, query: str, *, limit: int = 8) -> list[dict[str, Any]]:
        result = self.search(text=query, limit=limit)
        sources: list[dict[str, Any]] = []
        for row in result.get("items", []):
            detail = self.get_standard(row["standard_uid"], include_proposed_weak=False)
            if not detail:
                continue
            quotes = detail.get("quotes") or []
            primary = quotes[0] if quotes else {}
            sources.append({
                "source_type": "legal_standard",
                "standard_uid": detail["standard_uid"],
                "title": detail["statement"],
                "statement": detail["statement"],
                "speaker": detail["speaker"],
                "source_speaker": detail["source_speaker"],
                "treatment": detail["treatment"],
                "document_name": detail["document_name"],
                "document_path": detail["document_path"],
                "court": detail["court"],
                "judgment_date": detail["judgment_date"],
                "quote": primary.get("quote_text", ""),
                "page_start": primary.get("page_start"),
                "page_end": primary.get("page_end"),
                "tags": detail.get("tags", []),
                "publication_status": detail["publication_status"],
            })
        return sources
