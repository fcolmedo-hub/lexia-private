from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from storage.jurisprudence_content_probe import extract
from storage.jurisprudence_index import ensure_jurisprudence_index


# Política conservadora: precisión antes que cobertura.
# La carátula todavía no se persiste automáticamente porque la muestra real
# mostró encabezados truncados o narrativos en algunos tribunales.
MIN_CONFIDENCE = {
    "court": 0.99,
    "chamber": 0.90,
    "date": 0.95,
    "case_number": 0.95,
}


def _load_confidence(raw: str) -> dict:
    try:
        value = json.loads(raw or "{}")
    except Exception:
        return {}
    return value if isinstance(value, dict) else {}


def _remove_content_confidence(confidence: dict) -> dict:
    """Drop only values managed by the automatic content extractor."""
    for key in (
        "decision_court_name",
        "decision_chamber",
        "decision_chamber_value",
        "decision_date",
        "case_number",
    ):
        confidence.pop(key, None)
    return confidence


def update_content_index(database_path: str | Path) -> dict[str, int]:
    """Persist only high-confidence legal metadata from judgment text.

    The folder tree is used as contextual veto, never as proof of the exact
    deciding court. Re-running this function replaces previous automatically
    extracted values, so rules that become stricter also remove stale false
    positives. Documents, fragments, FTS and Qdrant are not modified.
    """
    connection = sqlite3.connect(Path(database_path), timeout=30)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA busy_timeout = 30000")
    connection.execute("PRAGMA foreign_keys = ON")

    stats = {
        "scanned": 0,
        "with_text": 0,
        "updated_documents": 0,
        "court": 0,
        "chamber": 0,
        "date": 0,
        "case_number": 0,
        "cleared_auto_values": 0,
    }

    try:
        ensure_jurisprudence_index(connection)

        rows = connection.execute(
            """
            SELECT
                d.path,
                d.text_content,
                COALESCE(j.scope, '') AS scope,
                COALESCE(j.province, '') AS province,
                COALESCE(j.hierarchy_group, '') AS hierarchy_group,
                COALESCE(j.decision_court_name, '') AS old_court,
                COALESCE(j.decision_chamber, '') AS old_chamber,
                COALESCE(j.decision_date, '') AS old_date,
                COALESCE(j.case_number, '') AS old_case_number,
                COALESCE(j.decision_court_source, '') AS old_court_source,
                COALESCE(j.confidence_json, '{}') AS confidence_json
            FROM documents d
            JOIN jurisprudence_index j ON j.document_path = d.path
            WHERE COALESCE(d.is_deleted, 0) = 0
              AND d.category = 'Jurisprudencia'
            ORDER BY d.path COLLATE NOCASE
            """
        ).fetchall()

        for row in rows:
            stats["scanned"] += 1
            text = str(row["text_content"] or "")
            if len(text.strip()) < 500:
                continue
            stats["with_text"] += 1

            context = {
                "scope": row["scope"],
                "province": row["province"],
                "hierarchy_group": row["hierarchy_group"],
            }
            result = extract(text, context=context)
            confidence = _remove_content_confidence(
                _load_confidence(row["confidence_json"])
            )

            court = str(result.get("court") or "").strip()
            court_conf = float(result.get("confidence", {}).get("court", 0.0) or 0.0)
            if not (court and court_conf >= MIN_CONFIDENCE["court"]):
                court = ""
                court_conf = 0.0
            else:
                confidence["decision_court_name"] = court_conf
                stats["court"] += 1

            chamber = str(result.get("chamber") or "").strip()
            chamber_conf = float(result.get("confidence", {}).get("chamber", 0.0) or 0.0)
            if not (chamber and chamber_conf >= MIN_CONFIDENCE["chamber"]):
                chamber = ""
                chamber_conf = 0.0
            else:
                confidence["decision_chamber"] = chamber_conf
                stats["chamber"] += 1

            decision_date = str(result.get("date") or "").strip()
            date_conf = float(result.get("confidence", {}).get("date", 0.0) or 0.0)
            if not (decision_date and date_conf >= MIN_CONFIDENCE["date"]):
                decision_date = ""
                date_conf = 0.0
            else:
                confidence["decision_date"] = date_conf
                stats["date"] += 1

            case_number = str(result.get("case_number") or "").strip()
            number_conf = float(result.get("confidence", {}).get("case_number", 0.0) or 0.0)
            if not (case_number and number_conf >= MIN_CONFIDENCE["case_number"]):
                case_number = ""
                number_conf = 0.0
            else:
                confidence["case_number"] = number_conf
                stats["case_number"] += 1

            old_values = (
                str(row["old_court"] or ""),
                str(row["old_chamber"] or ""),
                str(row["old_date"] or ""),
                str(row["old_case_number"] or ""),
            )
            new_values = (court, chamber, decision_date, case_number)
            stats["cleared_auto_values"] += sum(
                1 for old, new in zip(old_values, new_values) if old and not new
            )

            has_content = any(new_values)
            source = "path-organizational+content" if has_content else "path-organizational"
            court_source = "content-header" if court else ""

            connection.execute(
                """
                UPDATE jurisprudence_index
                SET decision_court_name = ?,
                    decision_court_source = ?,
                    decision_chamber = ?,
                    decision_date = ?,
                    case_number = ?,
                    metadata_source = ?,
                    confidence_json = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE document_path = ?
                """,
                (
                    court,
                    court_source,
                    chamber,
                    decision_date,
                    case_number,
                    source,
                    json.dumps(confidence, ensure_ascii=False, separators=(",", ":")),
                    str(row["path"]),
                ),
            )
            if old_values != new_values:
                stats["updated_documents"] += 1

        connection.commit()
        return stats
    finally:
        connection.close()
