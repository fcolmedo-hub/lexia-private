from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import sqlite3
import unicodedata
from collections import Counter
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB = REPO_ROOT / "runtime" / "standards" / "standards.sqlite3"
DEFAULT_OUTPUT = REPO_ROOT / "runtime" / "standards" / "canonicalization_candidates.jsonl"
DEFAULT_SUMMARY = REPO_ROOT / "runtime" / "standards" / "canonicalization_summary.json"

STOPWORDS = {
    "a", "al", "ante", "bajo", "con", "contra", "de", "del", "desde", "durante", "e", "el", "ella",
    "ellas", "ellos", "en", "entre", "es", "esa", "ese", "esta", "este", "ha", "hacia", "hasta", "la",
    "las", "lo", "los", "más", "mediante", "ni", "no", "o", "para", "pero", "por", "que", "se", "según",
    "ser", "si", "sin", "sobre", "su", "sus", "también", "un", "una", "uno", "y", "ya",
    "debe", "deben", "puede", "pueden", "corresponde", "resulta", "respecto", "caso", "casos",
}

TOKEN_RE = re.compile(r"[a-z0-9áéíóúüñ]+", re.IGNORECASE)


def strip_accents(text: str) -> str:
    return "".join(ch for ch in unicodedata.normalize("NFD", text) if unicodedata.category(ch) != "Mn")


def normalize(text: Any) -> str:
    value = strip_accents(str(text or "").casefold())
    value = re.sub(r"\s+", " ", value).strip()
    return value


def tokens(text: Any) -> list[str]:
    result: list[str] = []
    for token in TOKEN_RE.findall(normalize(text)):
        if len(token) < 3 or token in STOPWORDS or token.isdigit():
            continue
        result.append(token)
    return result


def parse_json_list(value: Any) -> list[str]:
    if not value:
        return []
    try:
        parsed = json.loads(value) if isinstance(value, str) else value
    except json.JSONDecodeError:
        return []
    if not isinstance(parsed, list):
        return []
    return [str(x) for x in parsed if str(x).strip()]


def combined_text(row: sqlite3.Row) -> str:
    parts = [str(row["statement"] or "")]
    parts.extend(parse_json_list(row["conditions_json"]))
    if row["consequence"]:
        parts.append(str(row["consequence"]))
    parts.extend(parse_json_list(row["exceptions_json"]))
    return " ".join(parts)


def weighted_jaccard(a: Counter[str], b: Counter[str], idf: dict[str, float]) -> float:
    terms = set(a) | set(b)
    if not terms:
        return 0.0
    num = 0.0
    den = 0.0
    for term in terms:
        weight = idf.get(term, 1.0)
        num += min(a.get(term, 0), b.get(term, 0)) * weight
        den += max(a.get(term, 0), b.get(term, 0)) * weight
    return num / den if den else 0.0


def pair_uid(a_uid: str, b_uid: str) -> str:
    left, right = sorted((a_uid, b_uid))
    return "CAN-" + hashlib.sha256(f"{left}|{right}".encode("utf-8")).hexdigest()[:20]


def quote_excerpt(conn: sqlite3.Connection, standard_uid: str, max_chars: int = 700) -> str:
    rows = conn.execute(
        "SELECT quote_text FROM quotes WHERE standard_uid=? ORDER BY evidence_index LIMIT 2",
        (standard_uid,),
    ).fetchall()
    text = " […] ".join(str(row[0]) for row in rows if row[0])
    return text[:max_chars]


def build_candidates(
    conn: sqlite3.Connection,
    cross_min_score: float,
    cross_min_shared_terms: int,
    top_k_terms: int,
) -> list[dict[str, Any]]:
    """Preselector deliberadamente orientado a recall.

    Reglas:
    - Dentro de un mismo documento se conservan TODOS los pares. En una sentencia,
      reglas próximas pueden ser general/especial, excepción, apoyo o duplicado aunque
      compartan poco vocabulario literal.
    - Entre documentos se exige al menos una señal léxica: términos informativos
      compartidos y un score mínimo bajo. La decisión jurídica queda para la etapa
      posterior y nunca se infiere aquí.
    """
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        """
        SELECT s.standard_uid, s.document_id, s.statement, s.speaker, s.source_speaker, s.treatment,
               s.conditions_json, s.consequence, s.exceptions_json, s.review_status, s.publication_status,
               d.document_name, d.court, d.judgment_date
        FROM standards s
        JOIN documents d ON d.document_id=s.document_id
        WHERE s.review_status='validated' AND s.publication_status IN ('ready','published')
        ORDER BY s.standard_uid
        """
    ).fetchall()

    token_lists: dict[str, list[str]] = {}
    counters: dict[str, Counter[str]] = {}
    by_uid: dict[str, sqlite3.Row] = {}
    df: Counter[str] = Counter()

    for row in rows:
        uid = str(row["standard_uid"])
        by_uid[uid] = row
        toks = tokens(combined_text(row))
        token_lists[uid] = toks
        counters[uid] = Counter(toks)
        df.update(set(toks))

    n = max(len(rows), 1)
    idf = {term: math.log((n + 1) / (freq + 1)) + 1.0 for term, freq in df.items()}

    # Índice invertido sólo para generar candidatos cross-document de forma barata.
    inverted: dict[str, set[str]] = {}
    for uid, toks in token_lists.items():
        unique = sorted(set(toks), key=lambda t: (-idf.get(t, 0.0), t))[:top_k_terms]
        for term in unique:
            inverted.setdefault(term, set()).add(uid)

    pair_shared: Counter[tuple[str, str]] = Counter()
    for members in inverted.values():
        ordered = sorted(members)
        for i in range(len(ordered)):
            for j in range(i + 1, len(ordered)):
                pair_shared[(ordered[i], ordered[j])] += 1

    # Garantiza todos los pares dentro del mismo documento.
    by_document: dict[int, list[str]] = {}
    for row in rows:
        by_document.setdefault(int(row["document_id"]), []).append(str(row["standard_uid"]))

    all_pairs: dict[tuple[str, str], int] = dict(pair_shared)
    for members in by_document.values():
        ordered = sorted(members)
        for i in range(len(ordered)):
            for j in range(i + 1, len(ordered)):
                all_pairs.setdefault((ordered[i], ordered[j]), 0)

    output: list[dict[str, Any]] = []
    for (a_uid, b_uid), shared_terms in all_pairs.items():
        a = by_uid[a_uid]
        b = by_uid[b_uid]
        same_document = int(a["document_id"]) == int(b["document_id"])

        token_score = weighted_jaccard(counters[a_uid], counters[b_uid], idf)
        char_score = SequenceMatcher(None, normalize(a["statement"]), normalize(b["statement"])).ratio()
        score = round(0.72 * token_score + 0.28 * char_score, 6)

        if same_document:
            inclusion_reason = "same_document_recall"
        else:
            if shared_terms < cross_min_shared_terms or score < cross_min_score:
                continue
            inclusion_reason = "cross_document_lexical"

        output.append(
            {
                "candidate_id": pair_uid(a_uid, b_uid),
                "score": score,
                "shared_index_terms": int(shared_terms),
                "same_document": same_document,
                "inclusion_reason": inclusion_reason,
                "a": {
                    "standard_uid": a_uid,
                    "statement": a["statement"],
                    "speaker": a["speaker"],
                    "source_speaker": a["source_speaker"],
                    "treatment": a["treatment"],
                    "document_name": a["document_name"],
                    "court": a["court"],
                    "judgment_date": a["judgment_date"],
                    "evidence_excerpt": quote_excerpt(conn, a_uid),
                },
                "b": {
                    "standard_uid": b_uid,
                    "statement": b["statement"],
                    "speaker": b["speaker"],
                    "source_speaker": b["source_speaker"],
                    "treatment": b["treatment"],
                    "document_name": b["document_name"],
                    "court": b["court"],
                    "judgment_date": b["judgment_date"],
                    "evidence_excerpt": quote_excerpt(conn, b_uid),
                },
            }
        )

    output.sort(
        key=lambda x: (
            -int(bool(x["same_document"])),
            -float(x["score"]),
            str(x["candidate_id"]),
        )
    )
    return output


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Genera pares candidatos para canonicalización sin decidir automáticamente la relación jurídica."
    )
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--summary", type=Path, default=DEFAULT_SUMMARY)
    parser.add_argument("--cross-min-score", type=float, default=0.08)
    parser.add_argument("--cross-min-shared-terms", type=int, default=1)
    parser.add_argument("--top-k-terms", type=int, default=24)
    args = parser.parse_args()

    if not args.db.exists():
        parser.error(f"No existe la base: {args.db}")

    conn = sqlite3.connect(args.db)
    try:
        candidates = build_candidates(
            conn,
            args.cross_min_score,
            args.cross_min_shared_terms,
            args.top_k_terms,
        )
        validated = conn.execute(
            "SELECT COUNT(*) FROM standards WHERE review_status='validated' AND publication_status IN ('ready','published')"
        ).fetchone()[0]
    finally:
        conn.close()

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8") as fh:
        for item in candidates:
            fh.write(json.dumps(item, ensure_ascii=False, separators=(",", ":")) + "\n")

    summary = {
        "standards_considered": int(validated),
        "candidate_pairs": len(candidates),
        "same_document_pairs": sum(1 for x in candidates if x["same_document"]),
        "cross_document_pairs": sum(1 for x in candidates if not x["same_document"]),
        "cross_min_score": args.cross_min_score,
        "cross_min_shared_terms": args.cross_min_shared_terms,
        "top_k_terms": args.top_k_terms,
        "same_document_policy": "all_pairs_for_recall",
        "decision_policy": "prefilter_only_no_automatic_legal_relation",
        "output": str(args.output.resolve()),
    }
    args.summary.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
