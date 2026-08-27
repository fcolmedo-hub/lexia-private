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

    # No usar \b alrededor de "c/" o "s/": la barra y el espacio son ambos
    # caracteres no alfanuméricos y, por lo tanto, no existe word-boundary.
    # Exigimos separadores reales de carátula en posiciones tokenizadas.
    has_adversarial_marker = bool(
        re.search(r"(?:^|\s)(?:c/|contra)(?=\s)", title, re.I)
    )
    has_proceeding_marker = bool(
        re.search(r"(?:^|\s)s/(?=\s|[A-ZÁÉÍÓÚÑ])", title, re.I)
    )
    if not (has_adversarial_marker or has_proceeding_marker):
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

    # No eliminar el punto final: puede formar parte de una razón social
    # (S.A., S.R.L., S.A.S., etc.). Sólo limpiamos comillas y separadores
    # inequívocamente externos a la denominación de la parte.
    plaintiff = re.sub(r"\s+", " ", match.group(1)).strip(' “"”,;:-')
    defendant = re.sub(r"\s+", " ", match.group(2)).strip(' “"”,;:-')
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
            if len(text.strip()) < 500:
                continue
            stats["with_text"] += 1

            context = {
                "scope": row["scope"],
                "province": row["province"],
                "hierarchy_group": row["hierarchy_group"],
            }
            result = extract(text, context=context)
            metadata = _load_metadata(row["metadata_json"])
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

            extracted_title = str(result.get("case_title") or "").strip()
            title_conf = float(result.get("confidence", {}).get("case_title", 0.0) or 0.0)
            metadata_title = _safe_metadata_title(
                metadata.get("title")
                or metadata.get("case_title")
                or metadata.get("caratula")
                or ""
            )
            case_title = ""
            if extracted_title and title_conf >= MIN_CONFIDENCE["case_title"]:
                case_title = _safe_metadata_title(extracted_title)
            if not case_title and metadata_title:
                case_title = metadata_title
                title_conf = 0.99
            if case_title:
                confidence["case_title"] = title_conf or 0.95
                stats["case_title"] += 1

            plaintiff, defendant = _parse_parties(case_title)
            if plaintiff and defendant:
                confidence["plaintiff"] = confidence.get("case_title", 0.95)
                confidence["defendant"] = confidence.get("case_title", 0.95)
                stats["parties"] += 1

            laws = _split_values(metadata.get("laws") or metadata.get("normas"))[:50]
            articles = _split_values(metadata.get("articles") or metadata.get("articulos"))[:80]
            topics = _topics_from_metadata(metadata)
            if laws:
                confidence["laws"] = 1.0
                stats["laws"] += 1
            if articles:
                confidence["articles"] = 1.0
                stats["articles"] += 1
            if topics:
                confidence["legal_topics"] = 1.0
                stats["legal_topics"] += 1

            laws_json = json.dumps(laws, ensure_ascii=False, separators=(",", ":"))
            articles_json = json.dumps(articles, ensure_ascii=False, separators=(",", ":"))
            topics_json = json.dumps(topics, ensure_ascii=False, separators=(",", ":"))

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
                court,
                chamber,
                decision_date,
                case_number,
                case_title,
                plaintiff,
                defendant,
                laws_json,
                articles_json,
                topics_json,
            )
            stats["cleared_auto_values"] += sum(
                1 for old, new in zip(old_values[:7], new_values[:7]) if old and not new
            )

            has_content = any(new_values[:7]) or bool(laws or articles or topics)
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
