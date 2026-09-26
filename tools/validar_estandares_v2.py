from __future__ import annotations

import argparse
import json
import re
import unicodedata
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_FALLOS = REPO_ROOT / "runtime" / "standards_pilot" / "export_50_v2" / "fallos.jsonl"


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as fh:
        for lineno, raw in enumerate(fh, start=1):
            raw = raw.strip()
            if not raw:
                continue
            value = json.loads(raw)
            if not isinstance(value, dict):
                raise RuntimeError(f"Registro no-objeto en {path}, línea {lineno}")
            rows.append(value)
    return rows


def normalize_ws(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def canonicalize_whitespace_quote(source: str, quote: str) -> str | None:
    """Recupera el tramo literal del source si sólo difieren espacios/saltos."""
    if quote in source:
        return quote

    target = normalize_ws(quote)
    if not target:
        return None

    normalized_chars: list[str] = []
    source_positions: list[int] = []
    in_ws = False
    for idx, ch in enumerate(source):
        if ch.isspace():
            if not in_ws:
                normalized_chars.append(" ")
                source_positions.append(idx)
                in_ws = True
        else:
            normalized_chars.append(ch)
            source_positions.append(idx)
            in_ws = False

    full_normalized = "".join(normalized_chars)
    start_full = full_normalized.find(target)
    if start_full < 0:
        return None
    end_full = start_full + len(target) - 1
    if start_full >= len(source_positions) or end_full >= len(source_positions):
        return None
    start_src = source_positions[start_full]
    end_src = source_positions[end_full] + 1
    return source[start_src:end_src]


def _compact_with_positions(text: str) -> tuple[str, list[int]]:
    """NFKC + elimina sólo whitespace, conservando puntuación/acentos y mapa al original."""
    chars: list[str] = []
    positions: list[int] = []
    for idx, original in enumerate(text):
        normalized = unicodedata.normalize("NFKC", original)
        for ch in normalized:
            if ch.isspace():
                continue
            chars.append(ch)
            positions.append(idx)
    return "".join(chars), positions


def canonicalize_ocr_spacing_quote(source: str, quote: str) -> str | None:
    """
    Recupera una cita literal cuando el OCR insertó espacios dentro de palabras.
    Exige al menos 30 caracteres no-blancos y una aparición única.
    """
    compact_quote, _ = _compact_with_positions(quote)
    if len(compact_quote) < 30:
        return None

    compact_source, positions = _compact_with_positions(source)
    first = compact_source.find(compact_quote)
    if first < 0:
        return None
    if compact_source.find(compact_quote, first + 1) >= 0:
        return None

    end = first + len(compact_quote) - 1
    if first >= len(positions) or end >= len(positions):
        return None
    return source[positions[first] : positions[end] + 1]


def _fuzzy_normalize_with_positions(text: str) -> tuple[str, list[int]]:
    """
    Normalización sólo para localizar candidatos OCR: minúsculas, sin diacríticos,
    sin whitespace ni puntuación. Nunca se almacena esta versión; se usa para
    recuperar un tramo literal del chunk original.
    """
    chars: list[str] = []
    positions: list[int] = []
    for idx, original in enumerate(text):
        decomposed = unicodedata.normalize("NFKD", original)
        for ch in decomposed:
            if unicodedata.combining(ch):
                continue
            ch = ch.casefold()
            if not ch.isalnum():
                continue
            chars.append(ch)
            positions.append(idx)
    return "".join(chars), positions


def canonicalize_fuzzy_ocr_quote(source: str, quote: str) -> tuple[str | None, float | None]:
    """
    Último recurso conservador para OCR que cambió pocos caracteres además de espacios.

    Sólo certifica si:
    - la cita normalizada tiene >= 45 caracteres;
    - la mejor ventana alcanza similitud >= 0.94;
    - no existe otra ventana no solapada casi igual (margen >= 0.025).

    Devuelve siempre el texto literal del chunk, nunca la versión del modelo.
    """
    target, _ = _fuzzy_normalize_with_positions(quote)
    source_norm, positions = _fuzzy_normalize_with_positions(source)
    if len(target) < 45 or len(source_norm) < len(target) // 2 or not positions:
        return None, None

    matcher = SequenceMatcher(None, target, source_norm, autojunk=False)
    longest = matcher.find_longest_match(0, len(target), 0, len(source_norm))
    if longest.size < max(18, int(len(target) * 0.35)):
        return None, None

    estimated_start = max(0, longest.b - longest.a)
    target_len = len(target)
    starts = range(max(0, estimated_start - 24), min(len(source_norm), estimated_start + 25))
    deltas = (-10, -6, -3, 0, 3, 6, 10)

    candidates: list[tuple[float, int, int]] = []
    for start in starts:
        for delta in deltas:
            length = target_len + delta
            if length < 35:
                continue
            end = start + length
            if end > len(source_norm):
                continue
            ratio = SequenceMatcher(None, target, source_norm[start:end], autojunk=False).ratio()
            candidates.append((ratio, start, end))

    if not candidates:
        return None, None
    candidates.sort(reverse=True, key=lambda x: x[0])
    best_ratio, best_start, best_end = candidates[0]
    if best_ratio < 0.94:
        return None, best_ratio

    second_ratio = 0.0
    for ratio, start, end in candidates[1:]:
        # Sólo cuenta como competidor un tramo sustancialmente distinto.
        overlap = max(0, min(best_end, end) - max(best_start, start))
        union = max(best_end, end) - min(best_start, start)
        overlap_ratio = overlap / union if union else 1.0
        if overlap_ratio < 0.50:
            second_ratio = ratio
            break
    if second_ratio and (best_ratio - second_ratio) < 0.025:
        return None, best_ratio

    if best_start >= len(positions) or best_end - 1 >= len(positions):
        return None, best_ratio
    literal = source[positions[best_start] : positions[best_end - 1] + 1]
    return literal, best_ratio


def validate_result(document: dict[str, Any], response_text: str) -> dict[str, Any]:
    parsed = json.loads(response_text)
    if not isinstance(parsed, list):
        raise ValueError("La respuesta raíz no es un array")

    chunks = {
        str(f.get("chunk_id")): f
        for f in document.get("fragments", [])
        if isinstance(f, dict) and f.get("chunk_id")
    }

    standards: list[dict[str, Any]] = []
    issues: list[dict[str, Any]] = []
    exact_quotes = 0
    canonicalized_quotes = 0
    ocr_spacing_canonicalized_quotes = 0
    fuzzy_ocr_canonicalized_quotes = 0
    invalid_quotes = 0

    for index, item in enumerate(parsed, start=1):
        if not isinstance(item, dict):
            issues.append({"standard": index, "type": "not_object"})
            continue
        standard = dict(item)
        standard["identifier"] = f"E{index}"
        quotes = item.get("quotes")
        if not isinstance(quotes, list) or not quotes:
            issues.append({"standard": index, "type": "missing_quotes"})
            standard["quotes"] = []
            standards.append(standard)
            continue

        canonical_quotes: list[dict[str, Any]] = []
        for q_index, quote in enumerate(quotes, start=1):
            if not isinstance(quote, dict):
                issues.append({"standard": index, "quote": q_index, "type": "quote_not_object"})
                invalid_quotes += 1
                continue
            chunk_id = str(quote.get("chunk_id") or "")
            chunk = chunks.get(chunk_id)
            if chunk is None:
                issues.append({
                    "standard": index,
                    "quote": q_index,
                    "type": "unknown_chunk_id",
                    "chunk_id": chunk_id,
                })
                invalid_quotes += 1
                continue
            text = str(quote.get("text") or "")
            source = str(chunk.get("text") or "")
            fuzzy_score: float | None = None
            if text and text in source:
                canonical = text
                exact_quotes += 1
                status = "exact"
            else:
                canonical = canonicalize_whitespace_quote(source, text)
                if canonical is not None:
                    canonicalized_quotes += 1
                    status = "whitespace_canonicalized"
                else:
                    canonical = canonicalize_ocr_spacing_quote(source, text)
                    if canonical is not None:
                        ocr_spacing_canonicalized_quotes += 1
                        status = "ocr_spacing_canonicalized"
                    else:
                        canonical, fuzzy_score = canonicalize_fuzzy_ocr_quote(source, text)
                        if canonical is not None:
                            fuzzy_ocr_canonicalized_quotes += 1
                            status = "fuzzy_ocr_canonicalized"
                        else:
                            invalid_quotes += 1
                            issues.append({
                                "standard": index,
                                "quote": q_index,
                                "type": "quote_not_found",
                                "chunk_id": chunk_id,
                                "model_quote": text,
                                "best_fuzzy_score": (
                                    round(fuzzy_score, 4) if fuzzy_score is not None else None
                                ),
                            })
                            continue

            stored_quote = {
                "chunk_id": chunk_id,
                "page_start": chunk.get("page_start"),
                "page_end": chunk.get("page_end"),
                "text": canonical,
                "validation": status,
            }
            if fuzzy_score is not None:
                stored_quote["fuzzy_score"] = round(fuzzy_score, 4)
            canonical_quotes.append(stored_quote)

        standard["quotes"] = canonical_quotes
        standards.append(standard)

    return {
        "standards": standards,
        "validation": {
            "standards_count": len(standards),
            "exact_quotes": exact_quotes,
            "canonicalized_quotes": canonicalized_quotes,
            "ocr_spacing_canonicalized_quotes": ocr_spacing_canonicalized_quotes,
            "fuzzy_ocr_canonicalized_quotes": fuzzy_ocr_canonicalized_quotes,
            "invalid_quotes": invalid_quotes,
            "issues": issues,
            "needs_review": bool(issues),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Valida trazabilidad de respuestas v2 y deriva páginas desde los chunks.")
    parser.add_argument("--fallos", type=Path, default=DEFAULT_FALLOS)
    parser.add_argument("--responses", type=Path, required=True, help="Carpeta con NNN_respuesta.txt")
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()

    if not args.fallos.exists():
        parser.error(f"No existe fallos.jsonl: {args.fallos}")
    if not args.responses.exists():
        parser.error(f"No existe carpeta de respuestas: {args.responses}")

    output = args.output or (args.responses / "validated")
    output.mkdir(parents=True, exist_ok=True)
    documents = load_jsonl(args.fallos)
    by_id = {int(row.get("pilot_id")): row for row in documents if row.get("pilot_id") is not None}

    summary = {
        "documents": 0,
        "standards": 0,
        "exact_quotes": 0,
        "canonicalized_quotes": 0,
        "ocr_spacing_canonicalized_quotes": 0,
        "fuzzy_ocr_canonicalized_quotes": 0,
        "invalid_quotes": 0,
        "needs_review": 0,
    }

    for response_path in sorted(args.responses.glob("*_respuesta.txt")):
        try:
            pilot_id = int(response_path.name.split("_", 1)[0])
        except ValueError:
            continue
        document = by_id.get(pilot_id)
        if document is None:
            print(f"OMITIDO {response_path.name}: pilot_id sin documento")
            continue
        try:
            result = validate_result(document, response_path.read_text(encoding="utf-8"))
        except Exception as exc:
            print(f"ERROR {response_path.name}: {type(exc).__name__}: {exc}")
            continue

        target = output / f"{pilot_id:03d}_validado.json"
        target.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        val = result["validation"]
        summary["documents"] += 1
        summary["standards"] += int(val["standards_count"])
        summary["exact_quotes"] += int(val["exact_quotes"])
        summary["canonicalized_quotes"] += int(val["canonicalized_quotes"])
        summary["ocr_spacing_canonicalized_quotes"] += int(val["ocr_spacing_canonicalized_quotes"])
        summary["fuzzy_ocr_canonicalized_quotes"] += int(val["fuzzy_ocr_canonicalized_quotes"])
        summary["invalid_quotes"] += int(val["invalid_quotes"])
        summary["needs_review"] += int(bool(val["needs_review"]))
        print(
            f"{response_path.name}: estándares={val['standards_count']}, "
            f"exactas={val['exact_quotes']}, espacios={val['canonicalized_quotes']}, "
            f"OCR-espacios={val['ocr_spacing_canonicalized_quotes']}, "
            f"OCR-fuzzy={val['fuzzy_ocr_canonicalized_quotes']}, inválidas={val['invalid_quotes']}"
        )

    (output / "resumen_validacion.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
