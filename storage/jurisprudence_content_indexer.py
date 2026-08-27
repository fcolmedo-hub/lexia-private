from __future__ import annotations

import json
import re
import sqlite3
from pathlib import Path

from storage.jurisprudence_content_probe import extract
from storage.jurisprudence_index import ensure_jurisprudence_index


# Política conservadora: precisión antes que cobertura.
MIN_CONFIDENCE = {
    "court": 0.99,
    "chamber": 0.90,
    "date": 0.95,
    "case_number": 0.95,
    "case_title": 0.95,
}


def _load_confidence(raw: str) -> dict:
    try:
        value = json.loads(raw or "{}")
    except Exception:
        return {}
    return value if isinstance(value, dict) else {}


def _load_metadata(raw: str) -> dict:
    try:
        value = json.loads(raw or "{}")
    except Exception:
        return {}
    return value if isinstance(value, dict) else {}


def _remove_content_confidence(confidence: dict) -> dict:
    """Drop only values managed by the automatic legal-content extractor."""
    for key in (
        "decision_court_name",
        "decision_chamber",
        "decision_chamber_value",
        "decision_date",
        "case_number",
        "case_title",
        "plaintiff",
        "defendant",
        "laws",
        "articles",
        "legal_topics",
    ):
        confidence.pop(key, None)
    return confidence


def _split_values(value) -> list[str]:
    if value is None:
        return []
    if isinstance(value, (list, tuple, set)):
        raw_values = [str(item) for item in value]
    else:
        raw_values = re.split(r"\s*\|\s*|\s*;\s*|\n+", str(value))
    result: list[str] = []
    seen: set[str] = set()
    for raw in raw_values:
        item = re.sub(r"\s+", " ", raw).strip(" ,;|.-")
        if len(item) < 2:
            continue
        key = item.casefold()
        if key in seen:
            continue
        seen.add(key)
        result.append(item)
    return result


def _safe_metadata_title(value: str) -> str:
    title = re.sub(r"\s+", " ", str(value or "")).strip(' “"”.,;:-')
    if not 8 <= len(title) <= 220:
        return ""
    if not re.search(r"\b(c/|contra|s/)\b", title, re.I):
        return ""
    bad = (
        "recurso de apelación", "interpone la actora", "deduce demanda",
        "iniciaron una demanda", "considerando", "resuelve",
    )
    if any(token in title.casefold() for token in bad):
        return ""
    return title


def _parse_parties(title: str) -> tuple[str, str]:
    value = str(title or "").strip()
    if not value:
        return "", ""
    match = re.search(r"^(.*?)\s+(?:c/|contra)\s+(.*?)(?:\s+s/|$)", value, re.I)
    if not match:
        return "", ""
    plaintiff = re.sub(r"\s+", " ", match.group(1)).strip(' “"”.,;:-')
    defendant = re.sub(r"\s+", " ", match.group(2)).strip(' “"”.,;:-')
    if not (2 <= len(plaintiff) <= 160 and 2 <= len(defendant) <= 160):
        return "", ""
    return plaintiff, defendant


def _topics_from_metadata(metadata: dict) -> list[str]:
    for key in ("legal_topics", "topics", "keywords", "subjects", "materia", "voces"):
        values = _split_values(metadata.get(key))
        if values:
            return values[:30]
    return []


def update_content_index(database_path: str | Path) -> dict[str, int]:
    """Persist conservative legal metadata for active jurisprudence.

    Sources are deliberately separated:
    * path/tree: organizational context only;
    * judgment text: deciding court, chamber, date, case number and explicit title;
    * existing document metadata: laws, articles and explicit topic labels.

    Re-running replaces previous automatically managed values, allowing stricter
    rules to remove stale false positives. Documents, fragments, FTS and Qdrant
    are never modified here.
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
        "case_title": 0,
        "parties": 0,
        "laws": 0,
        "articles": 0,
        "legal_topics": 0,
        "cleared_auto_values": 0,
    }

    try:
        ensure_jurisprudence_index(connection)

        rows = connection.execute(
            """
            SELECT
                d.path,
                d.text_content,
                COALESCE(d.metadata_json, '{}') AS metadata_json,
                COALESCE(j.scope, '') AS scope,
                COALESCE(j.province, '') AS province,
                COALESCE(j.hierarchy_group, '') AS hierarchy_group,
                COALESCE(j.decision_court_name, '') AS old_court,
                COALESCE(j.decision_chamber, '') AS old_chamber,
                COALESCE(j.decision_date, '') AS old_date,
                COALESCE(j.case_number, '') AS old_case_number,
                COALESCE(j.case_title, '') AS old_case_title,
                COALESCE(j.plaintiff, '') AS old_plaintiff,
                COALESCE(j.defendant, '') AS old_defendant,
                COALESCE(j.laws_json, '[]') AS old_laws_json,
                COALESCE(j.articles_json, '[]') AS old_articles_json,
                COALESCE(j.legal_topics_json, '[]') AS old_topics_json,
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
            metadata = _load_metadata(row["metadata_json"])
            result = {"confidence": {}}
            if len(text.strip()) >= 500:
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
            extracted_conf = result.get("confidence", {}) or {}

            def accepted(name: str, threshold_key: str) -> tuple[str, float]:
                value = str(result.get(name) or "").strip()
                score = float(extracted_conf.get(name, 0.0) or 0.0)
                if value and score >= MIN_CONFIDENCE[threshold_key]:
                    return value, score
                return "", 0.0

            court, court_conf = accepted("court", "court")
            chamber, chamber_conf = accepted("chamber", "chamber")
            decision_date, date_conf = accepted("date", "date")
            case_number, number_conf = accepted("case_number", "case_number")
            case_title, title_conf = accepted("case_title", "case_title")

            if not case_title:
                case_title = _safe_metadata_title(metadata.get("title", ""))
                title_conf = 0.90 if case_title else 0.0

            plaintiff, defendant = _parse_parties(case_title)
            laws = _split_values(metadata.get("laws"))[:100]
            articles = _split_values(metadata.get("articles"))[:150]
            legal_topics = _topics_from_metadata(metadata)

            if court:
                confidence["decision_court_name"] = court_conf
                stats["court"] += 1
            if chamber:
                confidence["decision_chamber"] = chamber_conf
                stats["chamber"] += 1
            if decision_date:
                confidence["decision_date"] = date_conf
                stats["date"] += 1
            if case_number:
                confidence["case_number"] = number_conf
                stats["case_number"] += 1
            if case_title:
                confidence["case_title"] = title_conf
                stats["case_title"] += 1
            if plaintiff and defendant:
                confidence["plaintiff"] = title_conf
                confidence["defendant"] = title_conf
                stats["parties"] += 1
            if laws:
                confidence["laws"] = 0.90
                stats["laws"] += 1
            if articles:
                confidence["articles"] = 0.90
                stats["articles"] += 1
            if legal_topics:
                confidence["legal_topics"] = 0.90
                stats["legal_topics"] += 1

            laws_json = json.dumps(laws, ensure_ascii=False, separators=(",", ":"))
            articles_json = json.dumps(articles, ensure_ascii=False, separators=(",", ":"))
            topics_json = json.dumps(legal_topics, ensure_ascii=False, separators=(",", ":"))

            old_values = (
                str(row["old_court"] or ""),
                str(row["old_chamber"] or ""),
                str(row["old_date"] or ""),
                str(row["old_case_number"] or ""),
                str(row["old_case_title"] or ""),
                str(row["old_plaintiff"] or ""),
                str(row["old_defendant"] or ""),
                str(row["old_laws_json"] or "[]"),
                str(row["old_articles_json"] or "[]"),
                str(row["old_topics_json"] or "[]"),
            )
            new_values = (
                court, chamber, decision_date, case_number, case_title,
                plaintiff, defendant, laws_json, articles_json, topics_json,
            )
            stats["cleared_auto_values"] += sum(
                1 for old, new in zip(old_values, new_values)
                if old not in ("", "[]") and new in ("", "[]")
            )

            has_content = any((
                court, chamber, decision_date, case_number, case_title,
                plaintiff, defendant, laws, articles, legal_topics,
            ))
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
                    case_title = ?,
                    plaintiff = ?,
                    defendant = ?,
                    laws_json = ?,
                    articles_json = ?,
                    legal_topics_json = ?,
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
                    case_title,
                    plaintiff,
                    defendant,
                    laws_json,
                    articles_json,
                    topics_json,
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
