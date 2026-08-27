from __future__ import annotations

import json
import re
import sqlite3
from collections import Counter
from datetime import datetime
from pathlib import Path

from config.settings import SETTINGS


def _json_list(raw: str) -> list[str]:
    try:
        value = json.loads(raw or "[]")
    except Exception:
        return []
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def _suspicious_case_number(value: str) -> bool:
    """Flag only structurally implausible case identifiers.

    Argentine judicial files can legitimately be short (e.g. 799, 425, 2953,
    3/10), so raw string length is not a useful quality criterion.
    """
    number = re.sub(r"\s+", " ", str(value or "")).strip()
    if not number:
        return False
    if not re.search(r"\d", number):
        return True
    compact = re.sub(r"[^0-9A-Za-z]", "", number)
    if len(compact) < 2:
        return True
    if len(number) > 45:
        return True
    return False


def build_jurisprudence_audit(database_path: str | Path | None = None) -> dict:
    """Build a compact, deterministic audit of the persisted jurisprudence index."""
    db = Path(database_path or SETTINGS.catalog_path)
    con = sqlite3.connect(db, timeout=30)
    con.row_factory = sqlite3.Row
    try:
        rows = con.execute(
            """
            SELECT
                d.name,
                j.document_path,
                COALESCE(j.hierarchy_group,'') AS hierarchy_group,
                COALESCE(j.scope,'') AS scope,
                COALESCE(j.province,'') AS province,
                COALESCE(j.decision_court_name,'') AS court,
                COALESCE(j.decision_chamber,'') AS chamber,
                COALESCE(j.decision_date,'') AS decision_date,
                COALESCE(j.case_number,'') AS case_number,
                COALESCE(j.case_title,'') AS case_title,
                COALESCE(j.plaintiff,'') AS plaintiff,
                COALESCE(j.defendant,'') AS defendant,
                COALESCE(j.laws_json,'[]') AS laws_json,
                COALESCE(j.articles_json,'[]') AS articles_json,
                COALESCE(j.legal_topics_json,'[]') AS topics_json,
                COALESCE(j.confidence_json,'{}') AS confidence_json
            FROM jurisprudence_index j
            JOIN documents d ON d.path = j.document_path
            WHERE COALESCE(d.is_deleted,0)=0
              AND d.category='Jurisprudencia'
            ORDER BY d.name COLLATE NOCASE
            """
        ).fetchall()
    finally:
        con.close()

    fields = (
        "court", "chamber", "decision_date", "case_number", "case_title",
        "plaintiff", "defendant", "laws", "articles", "topics",
    )
    coverage = Counter()
    records = []
    suspicious = []

    narrative_tokens = (
        " señaló ", " dispuso ", " consideró ", " resolvió ", " sostuvo ",
        " entendió ", " en los casos ", " contrario al ",
    )

    for row in rows:
        laws = _json_list(row["laws_json"])
        articles = _json_list(row["articles_json"])
        topics = _json_list(row["topics_json"])
        item = {
            "name": row["name"],
            "path": row["document_path"],
            "hierarchy_group": row["hierarchy_group"],
            "scope": row["scope"],
            "province": row["province"],
            "court": row["court"],
            "chamber": row["chamber"],
            "decision_date": row["decision_date"],
            "case_number": row["case_number"],
            "case_title": row["case_title"],
            "plaintiff": row["plaintiff"],
            "defendant": row["defendant"],
            "laws": laws,
            "articles": articles,
            "topics": topics,
        }
        for field in fields:
            if item[field]:
                coverage[field] += 1

        reasons = []
        court_cf = f" {item['court'].casefold()} "
        group_cf = item["hierarchy_group"].casefold()
        if item["court"] and any(token in court_cf for token in narrative_tokens):
            reasons.append("tribunal_parece_narrativo")
        if "csjn" in group_cf and item["chamber"]:
            reasons.append("csjn_con_sala")
        if "csjn" in group_cf and item["court"] and (
            "santa fe" in court_cf or "provincia" in court_cf
        ):
            reasons.append("csjn_con_corte_provincial")
        if _suspicious_case_number(item["case_number"]):
            reasons.append("expediente_formato_sospechoso")
        if bool(item["plaintiff"]) != bool(item["defendant"]):
            reasons.append("partes_incompletas")
        if reasons:
            suspicious.append({"name": item["name"], "reasons": reasons, "values": item})
        records.append(item)

    total = len(records)
    return {
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "database": str(db),
        "total_jurisprudence": total,
        "coverage": {
            field: {
                "count": int(coverage[field]),
                "percent": round((coverage[field] * 100.0 / total), 1) if total else 0.0,
            }
            for field in fields
        },
        "suspicious_count": len(suspicious),
        "suspicious": suspicious,
        "records": records,
    }


def write_jurisprudence_audit(database_path: str | Path | None = None) -> Path:
    report = build_jurisprudence_audit(database_path)
    logs = Path(SETTINGS.logs_path)
    logs.mkdir(parents=True, exist_ok=True)
    target = logs / "jurisprudence_index_audit.json"
    temp = target.with_suffix(".json.tmp")
    temp.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    temp.replace(target)
    return target
