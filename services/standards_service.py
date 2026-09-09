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


def _table_exists(con: sqlite3.Connection, name: str) -> bool:
    return con.execute(
        "SELECT 1 FROM sqlite_master WHERE type IN ('table','view') AND name=?",
        (name,),
    ).fetchone() is not None


def _canonical_ready(con: sqlite3.Connection) -> bool:
    return (
        _table_exists(con, "canonical_standards")
        and _table_exists(con, "standard_occurrences")
        and con.execute("SELECT 1 FROM canonical_standards LIMIT 1").fetchone()
        is not None
    )


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
            if _canonical_ready(con):
                return int(con.execute(
                    """SELECT COUNT(*) FROM canonical_standards c
                       WHERE c.status='confirmed' AND EXISTS(
                           SELECT 1 FROM standard_occurrences o
                           JOIN standards s ON s.standard_uid=o.standard_uid
                           WHERE o.canonical_uid=c.canonical_uid
                             AND s.review_status='validated'
                             AND s.publication_status IN ('ready','published')
                       )"""
                ).fetchone()[0])
            return int(con.execute(
                "SELECT COUNT(*) FROM standards s WHERE " + self._base_visibility_sql()
            ).fetchone()[0])

    def inventory(self) -> dict[str, int]:
        """Return transparent stored/published counts for the product header."""
        empty = {
            "canonical_standards_total": 0,
            "visible_canonical_standards": 0,
            "occurrences_total": 0,
            "visible_occurrences": 0,
            "reserved_occurrences": 0,
        }
        if not self.available():
            return empty
        with _ro_connect(self.db_path) as con:
            occurrences_total = int(con.execute(
                "SELECT COUNT(*) FROM standards WHERE review_status<>'rejected'"
            ).fetchone()[0])
            visible_occurrences = int(con.execute(
                "SELECT COUNT(*) FROM standards s WHERE " + self._base_visibility_sql()
            ).fetchone()[0])
            if _canonical_ready(con):
                canonical_total = int(con.execute(
                    "SELECT COUNT(*) FROM canonical_standards WHERE status='confirmed'"
                ).fetchone()[0])
                visible_canonical = int(con.execute(
                    """SELECT COUNT(*) FROM canonical_standards c
                       WHERE c.status='confirmed' AND EXISTS(
                           SELECT 1 FROM standard_occurrences o
                           JOIN standards s ON s.standard_uid=o.standard_uid
                           WHERE o.canonical_uid=c.canonical_uid
                             AND s.review_status='validated'
                             AND s.publication_status IN ('ready','published')
                       )"""
                ).fetchone()[0])
            else:
                canonical_total = occurrences_total
                visible_canonical = visible_occurrences
        return {
            "canonical_standards_total": canonical_total,
            "visible_canonical_standards": visible_canonical,
            "occurrences_total": occurrences_total,
            "visible_occurrences": visible_occurrences,
            "reserved_occurrences": max(0, occurrences_total - visible_occurrences),
        }

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

        with _ro_connect(self.db_path) as con:
            canonical = _canonical_ready(con)
        if canonical:
            return self._search_canonical(
                text=text,
                tags=tags,
                court=court,
                date_from=date_from,
                date_to=date_to,
                speaker=speaker,
                treatment=treatment,
                limit=limit,
                offset=offset,
            )

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

    def _search_canonical(
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
        tags = [str(value).strip() for value in (tags or []) if str(value).strip()]
        text = str(text or "").strip()
        where = ["c.status='confirmed'"]
        params: list[Any] = []
        joins: list[str] = []
        score_sql = "0.0 AS rank"

        if text:
            query = _fts_query(text)
            if query:
                joins.append(
                    "JOIN canonical_standards_fts f ON f.canonical_uid=c.canonical_uid"
                )
                where.append("f.canonical_standards_fts MATCH ?")
                params.append(query)
                score_sql = "bm25(canonical_standards_fts) AS rank"
            else:
                where.append("0")

        occurrence_where = [
            "o.canonical_uid=c.canonical_uid",
            "s.review_status='validated'",
            "s.publication_status IN ('ready','published')",
        ]
        occurrence_params: list[Any] = []
        if court:
            occurrence_where.append("LOWER(COALESCE(d.court,'')) LIKE LOWER(?)")
            occurrence_params.append(f"%{court.strip()}%")
        if date_from:
            occurrence_where.append("COALESCE(d.judgment_date,'') >= ?")
            occurrence_params.append(date_from.strip())
        if date_to:
            occurrence_where.append("COALESCE(d.judgment_date,'') <= ?")
            occurrence_params.append(date_to.strip())
        if speaker:
            occurrence_where.append("s.speaker=?")
            occurrence_params.append(speaker.strip())
        if treatment:
            occurrence_where.append("s.treatment=?")
            occurrence_params.append(treatment.strip())
        where.append(
            """EXISTS(SELECT 1 FROM standard_occurrences o
                       JOIN standards s ON s.standard_uid=o.standard_uid
                       JOIN documents d ON d.document_id=s.document_id
                       WHERE """ + " AND ".join(occurrence_where) + ")"
        )
        params.extend(occurrence_params)

        if tags:
            placeholders = ",".join("?" for _ in tags)
            where.append(
                f"""c.canonical_uid IN (
                       SELECT o2.canonical_uid FROM standard_occurrences o2
                       JOIN standards s2 ON s2.standard_uid=o2.standard_uid
                       JOIN standard_tags st ON st.standard_uid=s2.standard_uid
                       JOIN tags t ON t.tag_id=st.tag_id
                       WHERE s2.review_status='validated'
                         AND s2.publication_status IN ('ready','published')
                         AND t.name IN ({placeholders})
                       GROUP BY o2.canonical_uid
                       HAVING COUNT(DISTINCT t.name)=?
                   )"""
            )
            params.extend(tags)
            params.append(len(set(tags)))

        from_sql = (
            " FROM canonical_standards c "
            + " ".join(joins)
            + " JOIN standards rs ON rs.standard_uid=c.representative_standard_uid"
            + " JOIN documents rd ON rd.document_id=rs.document_id"
        )
        where_sql = " WHERE " + " AND ".join(where)
        order_sql = (
            " ORDER BY rank ASC,c.updated_at DESC,c.canonical_uid"
            if text
            else " ORDER BY c.updated_at DESC,c.canonical_uid"
        )
        counts = """
            (SELECT COUNT(*) FROM standard_occurrences oc
             JOIN standards sc ON sc.standard_uid=oc.standard_uid
             WHERE oc.canonical_uid=c.canonical_uid
               AND sc.review_status='validated'
               AND sc.publication_status IN ('ready','published')) AS occurrence_count,
            (SELECT COUNT(DISTINCT sc.document_id) FROM standard_occurrences oc
             JOIN standards sc ON sc.standard_uid=oc.standard_uid
             WHERE oc.canonical_uid=c.canonical_uid
               AND sc.review_status='validated'
               AND sc.publication_status IN ('ready','published')) AS document_count
        """
        select_sql = (
            "SELECT c.canonical_uid,c.statement,c.status,c.representative_standard_uid,"
            "rs.speaker,rs.source_speaker,rs.treatment,rd.document_name,rd.document_path,"
            "rd.court,rd.judgment_date," + counts + "," + score_sql
        )
        with _ro_connect(self.db_path) as con:
            total = int(con.execute(
                "SELECT COUNT(*) FROM (SELECT c.canonical_uid" + from_sql + where_sql + ")",
                params,
            ).fetchone()[0])
            rows = con.execute(
                select_sql + from_sql + where_sql + order_sql + " LIMIT ? OFFSET ?",
                [*params, max(1, min(int(limit), 200)), max(0, int(offset))],
            ).fetchall()
            items = []
            for row in rows:
                item = dict(row)
                # Compatibilidad con clientes anteriores: el identificador
                # navegable es ahora el canónico.
                item["standard_uid"] = item["canonical_uid"]
                items.append(item)
            filters = self.filter_values(con)
        return {
            "ok": True,
            "available": True,
            "canonical": True,
            "total": total,
            "items": items,
            "filters": filters,
        }

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
            if _canonical_ready(con):
                return self._canonical_detail(
                    con, uid, include_proposed_weak=include_proposed_weak
                )
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

    def get_occurrence(self, standard_uid: str) -> dict[str, Any] | None:
        if not self.available():
            return None
        uid = str(standard_uid or "").strip()
        if not uid:
            return None
        with _ro_connect(self.db_path) as con:
            return self._occurrence_detail(con, uid)

    def _occurrence_detail(
        self, con: sqlite3.Connection, uid: str
    ) -> dict[str, Any] | None:
        row = con.execute(
            """SELECT s.*,d.document_name,d.document_path,d.source_key,d.court,
                      d.judgment_date,d.metadata_json
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
        item["quotes"] = [dict(quote) for quote in con.execute(
            """SELECT evidence_index,chunk_id,page_start,page_end,unit_ids_json,
                      quote_text,validation
               FROM quotes WHERE standard_uid=? ORDER BY evidence_index""",
            (uid,),
        )]
        for quote in item["quotes"]:
            quote["unit_ids"] = _loads(quote.pop("unit_ids_json", "[]"), [])
        item["tags"] = [str(tag[0]) for tag in con.execute(
            """SELECT t.name FROM tags t JOIN standard_tags st ON st.tag_id=t.tag_id
               WHERE st.standard_uid=? ORDER BY t.name""",
            (uid,),
        )]
        return item

    def _canonical_detail(
        self,
        con: sqlite3.Connection,
        identifier: str,
        *,
        include_proposed_weak: bool,
    ) -> dict[str, Any] | None:
        canonical = con.execute(
            """SELECT c.* FROM canonical_standards c
               WHERE c.canonical_uid=? OR c.canonical_uid=(
                   SELECT o.canonical_uid FROM standard_occurrences o
                   WHERE o.standard_uid=?
               )
               LIMIT 1""",
            (identifier, identifier),
        ).fetchone()
        if canonical is None or str(canonical["status"]) != "confirmed":
            return None
        canonical_uid = str(canonical["canonical_uid"])
        occurrence_rows = con.execute(
            """SELECT o.standard_uid,o.match_basis,o.confidence
               FROM standard_occurrences o
               JOIN standards s ON s.standard_uid=o.standard_uid
               WHERE o.canonical_uid=? AND o.membership_status='confirmed'
                 AND s.review_status='validated'
                 AND s.publication_status IN ('ready','published')
               ORDER BY CASE WHEN o.standard_uid=? THEN 0 ELSE 1 END,
                        s.created_at,o.standard_uid""",
            (canonical_uid, canonical["representative_standard_uid"]),
        ).fetchall()
        occurrences: list[dict[str, Any]] = []
        for occurrence_row in occurrence_rows:
            occurrence = self._occurrence_detail(con, str(occurrence_row["standard_uid"]))
            if occurrence:
                occurrence["match_basis"] = occurrence_row["match_basis"]
                occurrence["canonical_confidence"] = occurrence_row["confidence"]
                occurrences.append(occurrence)
        if not occurrences:
            return None
        representative = next(
            (
                item
                for item in occurrences
                if item["standard_uid"] == canonical["representative_standard_uid"]
            ),
            occurrences[0],
        )
        tags = sorted(
            {tag for occurrence in occurrences for tag in occurrence.get("tags", [])},
            key=str.casefold,
        )
        item = dict(representative)
        item.update(
            {
                "canonical_uid": canonical_uid,
                "standard_uid": canonical_uid,
                "representative_standard_uid": canonical["representative_standard_uid"],
                "statement": canonical["statement"],
                "canonical_status": canonical["status"],
                "occurrence_count": len(occurrences),
                "document_count": len({occurrence["document_id"] for occurrence in occurrences}),
                "occurrences": occurrences,
                "tags": tags,
                "relations": self._canonical_relations_for(
                    con,
                    canonical_uid,
                    include_proposed_weak=include_proposed_weak,
                ),
                "canonical_suggestions": self._canonical_suggestions(
                    con, canonical_uid
                ),
            }
        )
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

    def _canonical_summary(
        self, con: sqlite3.Connection, canonical_uid: str
    ) -> dict[str, Any] | None:
        row = con.execute(
            """SELECT c.canonical_uid,c.statement,c.status,
                      rs.speaker,rs.treatment,rd.document_name,rd.court,rd.judgment_date,
                      (SELECT COUNT(*) FROM standard_occurrences oc
                       JOIN standards sc ON sc.standard_uid=oc.standard_uid
                       WHERE oc.canonical_uid=c.canonical_uid
                         AND sc.review_status='validated'
                         AND sc.publication_status IN ('ready','published')) occurrence_count,
                      (SELECT COUNT(DISTINCT sc.document_id) FROM standard_occurrences oc
                       JOIN standards sc ON sc.standard_uid=oc.standard_uid
                       WHERE oc.canonical_uid=c.canonical_uid
                         AND sc.review_status='validated'
                         AND sc.publication_status IN ('ready','published')) document_count
               FROM canonical_standards c
               JOIN standards rs ON rs.standard_uid=c.representative_standard_uid
               JOIN documents rd ON rd.document_id=rs.document_id
               WHERE c.canonical_uid=? AND c.status='confirmed'""",
            (canonical_uid,),
        ).fetchone()
        if row is None or int(row["occurrence_count"] or 0) == 0:
            return None
        item = dict(row)
        item["standard_uid"] = item["canonical_uid"]
        return item

    def _canonical_relations_for(
        self,
        con: sqlite3.Connection,
        canonical_uid: str,
        *,
        include_proposed_weak: bool,
    ) -> list[dict[str, Any]]:
        members = [str(row[0]) for row in con.execute(
            "SELECT standard_uid FROM standard_occurrences WHERE canonical_uid=?",
            (canonical_uid,),
        )]
        if not members:
            return []
        placeholders = ",".join("?" for _ in members)
        rows = con.execute(
            f"""SELECT r.relation_id,r.from_standard_uid,r.to_standard_uid,
                       r.relation_type,r.status,r.rationale
                FROM relations r
                WHERE (r.from_standard_uid IN ({placeholders})
                   OR r.to_standard_uid IN ({placeholders}))
                  AND r.status<>'rejected'
                ORDER BY r.relation_id""",
            [*members, *members],
        ).fetchall()
        member_set = set(members)
        output: list[dict[str, Any]] = []
        seen: set[tuple[str, str, str]] = set()
        for row in rows:
            relation_type = str(row["relation_type"])
            status = str(row["status"])
            if status != "confirmed" and (
                not include_proposed_weak or relation_type not in WEAK_PROPOSED_RELATIONS
            ):
                continue
            from_member = str(row["from_standard_uid"]) in member_set
            other_uid = (
                str(row["to_standard_uid"])
                if from_member
                else str(row["from_standard_uid"])
            )
            other_row = con.execute(
                "SELECT canonical_uid FROM standard_occurrences WHERE standard_uid=?",
                (other_uid,),
            ).fetchone()
            if other_row is None:
                continue
            other_canonical = str(other_row[0])
            if other_canonical == canonical_uid:
                continue
            direction = "out" if from_member else "in"
            key = (other_canonical, relation_type, direction)
            if key in seen:
                continue
            other = self._canonical_summary(con, other_canonical)
            if other is None:
                continue
            seen.add(key)
            output.append(
                {
                    "relation_id": row["relation_id"],
                    "relation_type": relation_type,
                    "status": status,
                    "direction": direction,
                    "rationale": row["rationale"],
                    "other": other,
                    "requires_confirmation": (
                        status == "proposed" and relation_type in STRONG_RELATIONS
                    ),
                }
            )
        return output

    def _canonical_suggestions(
        self, con: sqlite3.Connection, canonical_uid: str
    ) -> list[dict[str, Any]]:
        members = [str(row[0]) for row in con.execute(
            "SELECT standard_uid FROM standard_occurrences WHERE canonical_uid=?",
            (canonical_uid,),
        )]
        if not members:
            return []
        placeholders = ",".join("?" for _ in members)
        has_decisions = _table_exists(con, "relation_decisions")
        confidence_sql = (
            """(SELECT rd.confidence FROM relation_decisions rd
                 WHERE rd.relation_id=r.relation_id
                 ORDER BY CASE rd.decision_status WHEN 'reviewed' THEN 0 ELSE 1 END
                 LIMIT 1)"""
            if has_decisions
            else "NULL"
        )
        rows = con.execute(
            f"""SELECT r.relation_id,r.from_standard_uid,r.to_standard_uid,
                       r.rationale,{confidence_sql} AS confidence
                FROM relations r
                WHERE r.relation_type='duplicate_of' AND r.status='proposed'
                  AND (r.from_standard_uid IN ({placeholders})
                    OR r.to_standard_uid IN ({placeholders}))
                ORDER BY r.relation_id""",
            [*members, *members],
        ).fetchall()
        member_set = set(members)
        suggestions: list[dict[str, Any]] = []
        seen: set[str] = set()
        for row in rows:
            other_uid = (
                str(row["to_standard_uid"])
                if str(row["from_standard_uid"]) in member_set
                else str(row["from_standard_uid"])
            )
            other_row = con.execute(
                "SELECT canonical_uid FROM standard_occurrences WHERE standard_uid=?",
                (other_uid,),
            ).fetchone()
            if other_row is None:
                continue
            other_canonical = str(other_row[0])
            if other_canonical == canonical_uid or other_canonical in seen:
                continue
            other = self._canonical_summary(con, other_canonical)
            if other is None:
                continue
            seen.add(other_canonical)
            suggestions.append(
                {
                    "relation_id": row["relation_id"],
                    "relation_type": "duplicate_of",
                    "status": "proposed",
                    "confidence": row["confidence"],
                    "rationale": row["rationale"],
                    "other": other,
                    "label": "Posible misma regla",
                    "requires_confirmation": True,
                }
            )
        return suggestions

    def graph(self, standard_uid: str, *, depth: int = 1, include_proposed_weak: bool = True) -> dict[str, Any]:
        root = self.get_standard(standard_uid, include_proposed_weak=include_proposed_weak)
        if root is None:
            return {"ok": False, "error": "standard_not_found", "nodes": [], "edges": []}
        max_depth = max(1, min(int(depth), 3))
        root_uid = str(root["standard_uid"])
        nodes: dict[str, dict[str, Any]] = {root_uid: {k: root.get(k) for k in ("standard_uid", "canonical_uid", "statement", "speaker", "treatment", "document_name", "court", "judgment_date", "occurrence_count", "document_count")}}
        edges: dict[int, dict[str, Any]] = {}
        frontier = {root_uid}
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
        return {"ok": True, "root": root_uid, "nodes": list(nodes.values()), "edges": list(edges.values())}

    def investigation_sources(self, query: str, *, limit: int = 8) -> list[dict[str, Any]]:
        result = self.search(text=query, limit=limit)
        sources: list[dict[str, Any]] = []
        for row in result.get("items", []):
            detail = self.get_standard(row["standard_uid"], include_proposed_weak=False)
            if not detail:
                continue
            quotes = detail.get("quotes") or []
            primary = quotes[0] if quotes else {}
            supporting_sources = []
            for occurrence in detail.get("occurrences") or [detail]:
                occurrence_quotes = occurrence.get("quotes") or []
                occurrence_primary = occurrence_quotes[0] if occurrence_quotes else {}
                supporting_sources.append({
                    "standard_uid": occurrence.get("standard_uid"),
                    "wording": occurrence.get("statement"),
                    "speaker": occurrence.get("speaker"),
                    "source_speaker": occurrence.get("source_speaker"),
                    "treatment": occurrence.get("treatment"),
                    "document_name": occurrence.get("document_name"),
                    "document_path": occurrence.get("document_path"),
                    "court": occurrence.get("court"),
                    "judgment_date": occurrence.get("judgment_date"),
                    "quote": occurrence_primary.get("quote_text", ""),
                    "page_start": occurrence_primary.get("page_start"),
                    "page_end": occurrence_primary.get("page_end"),
                    "match_basis": occurrence.get("match_basis"),
                })
            sources.append({
                "source_type": "legal_standard",
                "standard_uid": detail["standard_uid"],
                "canonical_uid": detail.get("canonical_uid"),
                "representative_standard_uid": detail.get(
                    "representative_standard_uid", detail["standard_uid"]
                ),
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
                "occurrence_count": detail.get("occurrence_count", 1),
                "document_count": detail.get("document_count", 1),
                "supporting_sources": supporting_sources,
            })
        return sources
