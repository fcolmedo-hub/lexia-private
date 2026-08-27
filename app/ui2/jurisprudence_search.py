from __future__ import annotations

import json
import re
import sqlite3
from pathlib import Path

from config.settings import SETTINGS

# El marcador es un único término alfanumérico para que FTS/Boolean lo trate
# como texto normal e inexistente. Así el flujo pasa de forma segura al
# fallback profesional, donde se decodifica el filtro estructurado.
_MARKER_RE = re.compile(r"\s*LEXIAJURISX([0-9A-Fa-f]+)\s*", re.I)
_ALLOWED = {
    "court", "chamber", "scope", "province", "date_from", "date_to",
    "case_number", "party", "law", "text_query",
}


def parse_filter_envelope(query: str) -> tuple[str, dict[str, str]]:
    raw = str(query or "")
    match = _MARKER_RE.search(raw)
    if not match:
        return raw.strip(), {}
    try:
        decoded = bytes.fromhex(match.group(1)).decode("utf-8")
        value = json.loads(decoded)
    except Exception:
        value = {}
    filters = {}
    if isinstance(value, dict):
        for key in _ALLOWED:
            item = str(value.get(key, "") or "").strip()
            if item:
                filters[key] = item[:500 if key == "text_query" else 240]
    visible = re.sub(r"\s+", " ", _MARKER_RE.sub(" ", raw)).strip()
    transported_query = filters.pop("text_query", "")
    clean = visible or transported_query
    return clean, filters


def _like(value: str) -> str:
    return "%" + str(value or "").strip().replace("%", "") + "%"


def load_filtered_metadata(
    database_path: str | Path,
    filters: dict[str, str],
) -> dict[str, dict]:
    db = Path(database_path)
    if not db.exists():
        return {}
    where = ["COALESCE(d.is_deleted,0)=0", "d.category='Jurisprudencia'"]
    params: list[str] = []
    mapping = {
        "court": "j.decision_court_name",
        "chamber": "j.decision_chamber",
        "province": "j.province",
        "case_number": "j.case_number",
    }
    for key, column in mapping.items():
        if filters.get(key):
            where.append(f"COALESCE({column},'') LIKE ? COLLATE NOCASE")
            params.append(_like(filters[key]))
    if filters.get("scope"):
        where.append("COALESCE(j.scope,'') = ? COLLATE NOCASE")
        params.append(filters["scope"])
    if filters.get("date_from"):
        where.append("COALESCE(j.decision_date,'') >= ?")
        params.append(filters["date_from"])
    if filters.get("date_to"):
        where.append("COALESCE(j.decision_date,'') <= ?")
        params.append(filters["date_to"])
    if filters.get("party"):
        where.append("(COALESCE(j.plaintiff,'') LIKE ? COLLATE NOCASE OR COALESCE(j.defendant,'') LIKE ? COLLATE NOCASE OR COALESCE(j.case_title,'') LIKE ? COLLATE NOCASE)")
        pattern = _like(filters["party"])
        params.extend([pattern, pattern, pattern])
    if filters.get("law"):
        where.append("COALESCE(j.laws_json,'[]') LIKE ? COLLATE NOCASE")
        params.append(_like(filters["law"]))

    sql = f"""
        SELECT d.path,d.name,
               COALESCE(j.decision_court_name,'') AS court,
               COALESCE(j.decision_chamber,'') AS chamber,
               COALESCE(j.scope,'') AS scope,
               COALESCE(j.province,'') AS province,
               COALESCE(j.decision_date,'') AS decision_date,
               COALESCE(j.case_number,'') AS case_number,
               COALESCE(j.case_title,'') AS case_title,
               COALESCE(j.plaintiff,'') AS plaintiff,
               COALESCE(j.defendant,'') AS defendant,
               COALESCE(j.laws_json,'[]') AS laws_json,
               COALESCE(j.articles_json,'[]') AS articles_json
        FROM jurisprudence_index j
        JOIN documents d ON d.path=j.document_path
        WHERE {' AND '.join(where)}
        ORDER BY COALESCE(j.decision_date,'') DESC, d.name COLLATE NOCASE
    """
    con = sqlite3.connect(str(db), timeout=15)
    con.row_factory = sqlite3.Row
    try:
        rows = con.execute(sql, params).fetchall()
    finally:
        con.close()
    result = {}
    for row in rows:
        try:
            laws = json.loads(row["laws_json"] or "[]")
        except Exception:
            laws = []
        try:
            articles = json.loads(row["articles_json"] or "[]")
        except Exception:
            articles = []
        result[str(row["path"])] = {
            "court": row["court"], "chamber": row["chamber"],
            "scope": row["scope"], "province": row["province"],
            "decision_date": row["decision_date"], "case_number": row["case_number"],
            "case_title": row["case_title"], "plaintiff": row["plaintiff"],
            "defendant": row["defendant"], "laws": laws if isinstance(laws, list) else [],
            "articles": articles if isinstance(articles, list) else [],
        }
    return result


def metadata_bonus(metadata: dict, query: str) -> float:
    words = [w.casefold() for w in re.findall(r"[\wÁÉÍÓÚÑáéíóúñ]{3,}", str(query or ""))]
    if not words:
        return 0.0
    haystack = " ".join([
        str(metadata.get("court", "")), str(metadata.get("chamber", "")),
        str(metadata.get("case_number", "")), str(metadata.get("case_title", "")),
        str(metadata.get("plaintiff", "")), str(metadata.get("defendant", "")),
        " ".join(map(str, metadata.get("laws", []) or [])),
        " ".join(map(str, metadata.get("articles", []) or [])),
    ]).casefold()
    hits = sum(1 for word in set(words) if word in haystack)
    if not hits:
        return 0.0
    return min(float(SETTINGS.metadata_bonus) * 100.0, 2.0 + hits * 1.5)
