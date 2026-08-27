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


def update_content_index(database_path: str | Path) -> dict[str, int]:
    """Persist only high-confidence legal metadata from judgment text.

    The operation does not modify documents, fragments, FTS or Qdrant. Empty
    extractions never erase previously stored values.
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
    }

    try:
        ensure_jurisprudence_index(connection)

        rows = connection.execute(
            """
            SELECT
                d.path,
                d.text_content,
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

            result = extract(text)
            confidence = _load_confidence(row["confidence_json"])
            updates: dict[str, str] = {}

            court = str(result.get("court") or "").strip()
            court_conf = float(result.get("confidence", {}).get("court", 0.0) or 0.0)
            if court and court_conf >= MIN_CONFIDENCE["court"]:
                updates["decision_court_name"] = court
                updates["decision_court_source"] = "content-header"
                confidence["decision_court_name"] = court_conf
                stats["court"] += 1

            chamber = str(result.get("chamber") or "").strip()
            chamber_conf = float(result.get("confidence", {}).get("chamber", 0.0) or 0.0)
            if chamber and chamber_conf >= MIN_CONFIDENCE["chamber"]:
                updates["decision_chamber"] = chamber
                confidence["decision_chamber"] = chamber_conf
                stats["chamber"] += 1

            decision_date = str(result.get("date") or "").strip()
            date_conf = float(result.get("confidence", {}).get("date", 0.0) or 0.0)
            if decision_date and date_conf >= MIN_CONFIDENCE["date"]:
                updates["decision_date"] = decision_date
                confidence["decision_date"] = date_conf
                stats["date"] += 1

            case_number = str(result.get("case_number") or "").strip()
            number_conf = float(result.get("confidence", {}).get("case_number", 0.0) or 0.0)
            if case_number and number_conf >= MIN_CONFIDENCE["case_number"]:
                updates["case_number"] = case_number
                confidence["case_number"] = number_conf
                stats["case_number"] += 1

            if not updates:
                continue

            assignments = []
            values = []
            for column, value in updates.items():
                assignments.append(f"{column} = ?")
                values.append(value)

            assignments.extend([
                "metadata_source = 'path-organizational+content'",
                "confidence_json = ?",
                "updated_at = CURRENT_TIMESTAMP",
            ])
            values.append(json.dumps(confidence, ensure_ascii=False, separators=(",", ":")))
            values.append(str(row["path"]))

            connection.execute(
                f"UPDATE jurisprudence_index SET {', '.join(assignments)} WHERE document_path = ?",
                values,
            )
            stats["updated_documents"] += 1

        connection.commit()
        return stats
    finally:
        connection.close()
