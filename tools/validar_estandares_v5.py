from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from validar_estandares_v2 import load_jsonl

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_FALLOS = REPO_ROOT / "runtime" / "standards_pilot" / "export_50_v5" / "fallos.jsonl"


def validate_result(document: dict[str, Any], response_text: str) -> dict[str, Any]:
    parsed = json.loads(response_text)
    if not isinstance(parsed, dict) or not isinstance(parsed.get("standards"), list):
        raise ValueError("La respuesta v5 debe ser un objeto con standards=array")

    units: dict[str, dict[str, Any]] = {}
    chunks: dict[str, dict[str, Any]] = {}
    for fragment in document.get("fragments", []):
        if not isinstance(fragment, dict):
            continue
        chunk_id = str(fragment.get("chunk_id") or "")
        if not chunk_id:
            continue
        chunks[chunk_id] = fragment
        for unit in fragment.get("units", []):
            if not isinstance(unit, dict):
                continue
            unit_id = str(unit.get("unit_id") or "")
            if unit_id:
                units[unit_id] = {**unit, "chunk_id": chunk_id}

    output_standards: list[dict[str, Any]] = []
    issues: list[dict[str, Any]] = []
    evidence_total = 0
    evidence_resolved = 0
    invalid_evidence = 0

    for s_index, item in enumerate(parsed["standards"], start=1):
        if not isinstance(item, dict):
            issues.append({"standard": s_index, "type": "not_object"})
            continue
        standard = {k: v for k, v in item.items() if k != "evidence"}
        standard["identifier"] = f"E{s_index}"
        final_quotes: list[dict[str, Any]] = []
        evidence = item.get("evidence")
        if not isinstance(evidence, list) or not evidence:
            invalid_evidence += 1
            issues.append({"standard": s_index, "type": "missing_evidence"})
        else:
            for e_index, ev in enumerate(evidence, start=1):
                evidence_total += 1
                if not isinstance(ev, dict) or not isinstance(ev.get("unit_ids"), list) or not ev["unit_ids"]:
                    invalid_evidence += 1
                    issues.append({"standard": s_index, "evidence": e_index, "type": "invalid_unit_ids"})
                    continue
                unit_ids = [str(x) for x in ev["unit_ids"]]
                if len(set(unit_ids)) != len(unit_ids):
                    invalid_evidence += 1
                    issues.append({"standard": s_index, "evidence": e_index, "type": "duplicate_unit_ids", "unit_ids": unit_ids})
                    continue
                resolved = [units.get(uid) for uid in unit_ids]
                if any(x is None for x in resolved):
                    invalid_evidence += 1
                    issues.append({
                        "standard": s_index,
                        "evidence": e_index,
                        "type": "unknown_unit_id",
                        "unit_ids": unit_ids,
                        "unknown": [uid for uid, unit in zip(unit_ids, resolved) if unit is None],
                    })
                    continue
                known = [x for x in resolved if x is not None]
                chunk_ids = {str(x["chunk_id"]) for x in known}
                if len(chunk_ids) != 1:
                    invalid_evidence += 1
                    issues.append({"standard": s_index, "evidence": e_index, "type": "units_cross_chunks", "unit_ids": unit_ids})
                    continue
                indices = [int(x.get("unit_index")) for x in known]
                if indices != list(range(indices[0], indices[0] + len(indices))):
                    invalid_evidence += 1
                    issues.append({"standard": s_index, "evidence": e_index, "type": "units_not_contiguous_or_ordered", "unit_ids": unit_ids})
                    continue

                chunk_id = next(iter(chunk_ids))
                chunk = chunks[chunk_id]
                source = str(chunk.get("text") or "")
                start_offset = int(known[0].get("start_offset"))
                end_offset = int(known[-1].get("end_offset"))
                if not (0 <= start_offset < end_offset <= len(source)):
                    invalid_evidence += 1
                    issues.append({"standard": s_index, "evidence": e_index, "type": "invalid_offsets", "unit_ids": unit_ids})
                    continue
                literal = source[start_offset:end_offset]
                expected = "".join(str(x.get("text") or "") for x in known)
                if literal != expected:
                    invalid_evidence += 1
                    issues.append({"standard": s_index, "evidence": e_index, "type": "unit_partition_mismatch", "unit_ids": unit_ids})
                    continue

                evidence_resolved += 1
                final_quotes.append({
                    "unit_ids": unit_ids,
                    "chunk_id": chunk_id,
                    "page_start": chunk.get("page_start"),
                    "page_end": chunk.get("page_end"),
                    "text": literal,
                    "validation": "resolved_from_unit_ids",
                })

        standard["quotes"] = final_quotes
        output_standards.append(standard)

    return {
        "standards": output_standards,
        "validation": {
            "standards_count": len(output_standards),
            "evidence_total": evidence_total,
            "evidence_resolved": evidence_resolved,
            "invalid_evidence": invalid_evidence,
            "fuzzy_matching": 0,
            "issues": issues,
            "needs_review": bool(issues),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Valida v5 resolviendo evidencia exclusivamente por IDs deterministas de unidades.")
    parser.add_argument("--fallos", type=Path, default=DEFAULT_FALLOS)
    parser.add_argument("--responses", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()

    if not args.fallos.exists():
        parser.error(f"No existe fallos.jsonl: {args.fallos}")
    if not args.responses.exists():
        parser.error(f"No existe carpeta de respuestas: {args.responses}")

    output = args.output or (args.responses / "validated_v5")
    output.mkdir(parents=True, exist_ok=True)
    docs = load_jsonl(args.fallos)
    by_id = {int(row.get("pilot_id")): row for row in docs if row.get("pilot_id") is not None}

    summary = {
        "documents": 0,
        "standards": 0,
        "evidence_total": 0,
        "evidence_resolved": 0,
        "invalid_evidence": 0,
        "fuzzy_matching": 0,
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
            print(f"OMITIDO {response_path.name}: pilot_id sin documento")
            continue
        try:
            result = validate_result(document, response_path.read_text(encoding="utf-8"))
        except Exception as exc:
            summary["format_errors"] += 1
            print(f"ERROR {response_path.name}: {type(exc).__name__}: {exc}")
            continue

        (output / f"{pilot_id:03d}_validado.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        val = result["validation"]
        summary["documents"] += 1
        summary["standards"] += int(val["standards_count"])
        summary["evidence_total"] += int(val["evidence_total"])
        summary["evidence_resolved"] += int(val["evidence_resolved"])
        summary["invalid_evidence"] += int(val["invalid_evidence"])
        summary["needs_review"] += int(bool(val["needs_review"]))
        print(
            f"{response_path.name}: estándares={val['standards_count']}, evidencia={val['evidence_total']}, "
            f"resueltas={val['evidence_resolved']}, inválidas={val['invalid_evidence']}, fuzzy=0"
        )

    (output / "resumen_validacion.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
