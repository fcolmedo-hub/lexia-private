from __future__ import annotations

import argparse
import json
import re
import unicodedata
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

from validar_estandares_v2 import load_jsonl

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_FALLOS = REPO_ROOT / "runtime" / "standards_pilot" / "export_50_v4" / "fallos.jsonl"


def _normalize_ws_with_positions(text: str) -> tuple[str, list[int]]:
    chars: list[str] = []
    positions: list[int] = []
    in_ws = False
    for idx, ch in enumerate(text):
        if ch.isspace():
            if not in_ws:
                chars.append(" ")
                positions.append(idx)
                in_ws = True
        else:
            chars.append(ch)
            positions.append(idx)
            in_ws = False
    return "".join(chars), positions


def _compact_with_positions(text: str) -> tuple[str, list[int]]:
    chars: list[str] = []
    positions: list[int] = []
    for idx, original in enumerate(text):
        for ch in unicodedata.normalize("NFKC", original):
            if ch.isspace():
                continue
            chars.append(ch)
            positions.append(idx)
    return "".join(chars), positions


def _fuzzy_normalize_with_positions(text: str) -> tuple[str, list[int]]:
    chars: list[str] = []
    positions: list[int] = []
    for idx, original in enumerate(text):
        for ch in unicodedata.normalize("NFKD", original):
            if unicodedata.combining(ch):
                continue
            ch = ch.casefold()
            if ch.isalnum():
                chars.append(ch)
                positions.append(idx)
    return "".join(chars), positions


def _unique_find(haystack: str, needle: str) -> int | None:
    first = haystack.find(needle)
    if first < 0:
        return None
    if haystack.find(needle, first + 1) >= 0:
        return None
    return first


def locate_anchor(source: str, anchor: str) -> tuple[int, int, str, float | None] | None:
    anchor = anchor.strip()
    if not anchor:
        return None

    exact = _unique_find(source, anchor)
    if exact is not None:
        return exact, exact + len(anchor), "exact", None

    target_ws, _ = _normalize_ws_with_positions(anchor)
    source_ws, ws_pos = _normalize_ws_with_positions(source)
    pos = _unique_find(source_ws, target_ws)
    if pos is not None and target_ws:
        end = pos + len(target_ws) - 1
        if end < len(ws_pos):
            return ws_pos[pos], ws_pos[end] + 1, "whitespace", None

    target_compact, _ = _compact_with_positions(anchor)
    source_compact, compact_pos = _compact_with_positions(source)
    if len(target_compact) >= 18:
        pos = _unique_find(source_compact, target_compact)
        if pos is not None:
            end = pos + len(target_compact) - 1
            if end < len(compact_pos):
                return compact_pos[pos], compact_pos[end] + 1, "ocr_spacing", None

    target, _ = _fuzzy_normalize_with_positions(anchor)
    source_norm, source_pos = _fuzzy_normalize_with_positions(source)
    if len(target) < 24 or not source_norm or not source_pos:
        return None

    matcher = SequenceMatcher(None, target, source_norm, autojunk=False)
    longest = matcher.find_longest_match(0, len(target), 0, len(source_norm))
    if longest.size < max(12, int(len(target) * 0.45)):
        return None

    estimated_start = max(0, longest.b - longest.a)
    candidates: list[tuple[float, int, int]] = []
    for start in range(max(0, estimated_start - 18), min(len(source_norm), estimated_start + 19)):
        for delta in (-5, -3, 0, 3, 5):
            length = len(target) + delta
            if length < 20:
                continue
            end = start + length
            if end > len(source_norm):
                continue
            ratio = SequenceMatcher(None, target, source_norm[start:end], autojunk=False).ratio()
            candidates.append((ratio, start, end))
    if not candidates:
        return None
    candidates.sort(reverse=True, key=lambda x: x[0])
    best_ratio, best_start, best_end = candidates[0]
    if best_ratio < 0.95:
        return None

    competitor = 0.0
    for ratio, start, end in candidates[1:]:
        overlap = max(0, min(best_end, end) - max(best_start, start))
        union = max(best_end, end) - min(best_start, start)
        if union and overlap / union < 0.50:
            competitor = ratio
            break
    if competitor and best_ratio - competitor < 0.03:
        return None
    if best_end - 1 >= len(source_pos):
        return None
    return source_pos[best_start], source_pos[best_end - 1] + 1, "fuzzy_anchor", best_ratio


def reconstruct_quote(source: str, start_anchor: str, end_anchor: str) -> tuple[str | None, dict[str, Any]]:
    start = locate_anchor(source, start_anchor)
    end = locate_anchor(source, end_anchor)
    if start is None or end is None:
        return None, {
            "start_found": start is not None,
            "end_found": end is not None,
        }
    start_pos = start[0]
    end_pos = end[1]
    if end_pos <= start_pos:
        return None, {"reason": "end_before_start"}
    if end_pos - start_pos > 2500:
        return None, {"reason": "quote_too_long", "length": end_pos - start_pos}
    return source[start_pos:end_pos], {
        "start_validation": start[2],
        "end_validation": end[2],
        "start_fuzzy_score": round(start[3], 4) if start[3] is not None else None,
        "end_fuzzy_score": round(end[3], 4) if end[3] is not None else None,
    }


def validate_result(document: dict[str, Any], response_text: str) -> dict[str, Any]:
    parsed = json.loads(response_text)
    if not isinstance(parsed, dict) or not isinstance(parsed.get("standards"), list):
        raise ValueError("La respuesta v4 debe ser un objeto con standards=array")

    chunks = {
        str(f.get("chunk_id")): f
        for f in document.get("fragments", [])
        if isinstance(f, dict) and f.get("chunk_id")
    }
    output_standards: list[dict[str, Any]] = []
    issues: list[dict[str, Any]] = []
    evidence_total = 0
    reconstructed_quotes = 0
    invalid_evidence = 0
    fuzzy_anchor_quotes = 0

    for s_index, item in enumerate(parsed["standards"], start=1):
        if not isinstance(item, dict):
            issues.append({"standard": s_index, "type": "not_object"})
            continue
        standard = {k: v for k, v in item.items() if k != "evidence"}
        standard["identifier"] = f"E{s_index}"
        final_quotes: list[dict[str, Any]] = []
        evidence = item.get("evidence")
        if not isinstance(evidence, list) or not evidence:
            issues.append({"standard": s_index, "type": "missing_evidence"})
            invalid_evidence += 1
        else:
            for e_index, ev in enumerate(evidence, start=1):
                evidence_total += 1
                if not isinstance(ev, dict):
                    invalid_evidence += 1
                    issues.append({"standard": s_index, "evidence": e_index, "type": "evidence_not_object"})
                    continue
                chunk_id = str(ev.get("chunk_id") or "")
                chunk = chunks.get(chunk_id)
                if chunk is None:
                    invalid_evidence += 1
                    issues.append({"standard": s_index, "evidence": e_index, "type": "unknown_chunk_id", "chunk_id": chunk_id})
                    continue
                start_anchor = str(ev.get("start_anchor") or "")
                end_anchor = str(ev.get("end_anchor") or "")
                literal, details = reconstruct_quote(str(chunk.get("text") or ""), start_anchor, end_anchor)
                if literal is None:
                    invalid_evidence += 1
                    issues.append({
                        "standard": s_index,
                        "evidence": e_index,
                        "type": "anchors_not_reconstructed",
                        "chunk_id": chunk_id,
                        "start_anchor": start_anchor,
                        "end_anchor": end_anchor,
                        **details,
                    })
                    continue
                reconstructed_quotes += 1
                if details.get("start_validation") == "fuzzy_anchor" or details.get("end_validation") == "fuzzy_anchor":
                    fuzzy_anchor_quotes += 1
                final_quotes.append({
                    "chunk_id": chunk_id,
                    "page_start": chunk.get("page_start"),
                    "page_end": chunk.get("page_end"),
                    "text": literal,
                    "validation": "reconstructed_from_source",
                    "anchor_validation": details,
                })
        standard["quotes"] = final_quotes
        output_standards.append(standard)

    return {
        "standards": output_standards,
        "validation": {
            "standards_count": len(output_standards),
            "evidence_total": evidence_total,
            "reconstructed_quotes": reconstructed_quotes,
            "invalid_evidence": invalid_evidence,
            "fuzzy_anchor_quotes": fuzzy_anchor_quotes,
            "issues": issues,
            "needs_review": bool(issues),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Valida v4 y reconstruye citas literales desde start/end anchors.")
    parser.add_argument("--fallos", type=Path, default=DEFAULT_FALLOS)
    parser.add_argument("--responses", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()

    if not args.fallos.exists():
        parser.error(f"No existe fallos.jsonl: {args.fallos}")
    if not args.responses.exists():
        parser.error(f"No existe carpeta de respuestas: {args.responses}")

    output = args.output or (args.responses / "validated_v4")
    output.mkdir(parents=True, exist_ok=True)
    docs = load_jsonl(args.fallos)
    by_id = {int(row.get("pilot_id")): row for row in docs if row.get("pilot_id") is not None}

    summary = {
        "documents": 0,
        "standards": 0,
        "evidence_total": 0,
        "reconstructed_quotes": 0,
        "invalid_evidence": 0,
        "fuzzy_anchor_quotes": 0,
        "needs_review": 0,
        "format_errors": 0,
    }

    for response_path in sorted(args.responses.glob("*_respuesta.txt")):
        try:
            pilot_id = int(response_path.name.split("_", 1)[0])
        except ValueError:
            continue
        document = by_id.get(pilot_id)
        if document is None:
            continue
        try:
            result = validate_result(document, response_path.read_text(encoding="utf-8"))
        except Exception as exc:
            summary["format_errors"] += 1
            print(f"ERROR {response_path.name}: {type(exc).__name__}: {exc}")
            continue

        (output / f"{pilot_id:03d}_validado.json").write_text(
            json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        val = result["validation"]
        summary["documents"] += 1
        for key in ("standards", "evidence_total", "reconstructed_quotes", "invalid_evidence", "fuzzy_anchor_quotes"):
            source_key = "standards_count" if key == "standards" else key
            summary[key] += int(val[source_key])
        summary["needs_review"] += int(bool(val["needs_review"]))
        print(
            f"{response_path.name}: estándares={val['standards_count']}, evidencia={val['evidence_total']}, "
            f"reconstruidas={val['reconstructed_quotes']}, inválidas={val['invalid_evidence']}, "
            f"fuzzy-ancla={val['fuzzy_anchor_quotes']}"
        )

    (output / "resumen_validacion.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
