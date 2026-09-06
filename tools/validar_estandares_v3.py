from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from validar_estandares_v2 import load_jsonl, validate_result

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_FALLOS = REPO_ROOT / "runtime" / "standards_pilot" / "export_50_v3" / "fallos.jsonl"

SPEAKERS = {
    "m": "mayoria",
    "d": "disidencia",
    "p": "procurador",
    "t": "tribunal_anterior",
}
TREATMENTS = {
    "a": "adopta",
    "p": "propone",
    "c": "cita",
    "r": "rechaza",
}


def expand_compact_response(text: str) -> list[dict[str, Any]]:
    parsed = json.loads(text)
    if not isinstance(parsed, list):
        raise ValueError("La respuesta raíz no es un array")

    expanded: list[dict[str, Any]] = []
    for index, row in enumerate(parsed, start=1):
        if not isinstance(row, list) or len(row) != 8:
            raise ValueError(f"Estándar {index}: se esperaba array de 8 elementos")

        statement, speaker_code, source_code, treatment_code, conditions, consequence, exceptions, quote_rows = row
        if speaker_code not in SPEAKERS:
            raise ValueError(f"Estándar {index}: speaker inválido {speaker_code!r}")
        if source_code not in SPEAKERS:
            raise ValueError(f"Estándar {index}: source_speaker inválido {source_code!r}")
        if treatment_code not in TREATMENTS:
            raise ValueError(f"Estándar {index}: treatment inválido {treatment_code!r}")
        if not isinstance(conditions, list):
            raise ValueError(f"Estándar {index}: conditions debe ser array")
        if consequence is not None and not isinstance(consequence, str):
            raise ValueError(f"Estándar {index}: consequence debe ser string o null")
        if not isinstance(exceptions, list):
            raise ValueError(f"Estándar {index}: exceptions debe ser array")
        if not isinstance(quote_rows, list) or not quote_rows:
            raise ValueError(f"Estándar {index}: quotes debe contener al menos una cita")

        quotes: list[dict[str, str]] = []
        for q_index, q in enumerate(quote_rows, start=1):
            if not isinstance(q, list) or len(q) != 2:
                raise ValueError(f"Estándar {index}, cita {q_index}: se esperaba [chunk_id,text]")
            chunk_id, quote_text = q
            quotes.append({"chunk_id": str(chunk_id), "text": str(quote_text)})

        expanded.append(
            {
                "statement": str(statement),
                "speaker": SPEAKERS[speaker_code],
                "source_speaker": SPEAKERS[source_code],
                "treatment": TREATMENTS[treatment_code],
                "conditions": [str(x) for x in conditions],
                "consequence": consequence,
                "exceptions": [str(x) for x in exceptions],
                "quotes": quotes,
            }
        )
    return expanded


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Expande la salida compacta v3 y valida trazabilidad con el validador v2."
    )
    parser.add_argument("--fallos", type=Path, default=DEFAULT_FALLOS)
    parser.add_argument("--responses", type=Path, required=True)
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
            expanded = expand_compact_response(response_path.read_text(encoding="utf-8"))
            result = validate_result(document, json.dumps(expanded, ensure_ascii=False))
        except Exception as exc:
            summary["format_errors"] += 1
            print(f"ERROR {response_path.name}: {type(exc).__name__}: {exc}")
            continue

        target = output / f"{pilot_id:03d}_validado.json"
        target.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        val = result["validation"]
        summary["documents"] += 1
        summary["standards"] += int(val["standards_count"])
        summary["exact_quotes"] += int(val.get("exact_quotes", 0))
        summary["canonicalized_quotes"] += int(val.get("canonicalized_quotes", 0))
        summary["ocr_spacing_canonicalized_quotes"] += int(val.get("ocr_spacing_canonicalized_quotes", 0))
        summary["fuzzy_ocr_canonicalized_quotes"] += int(val.get("fuzzy_ocr_canonicalized_quotes", 0))
        summary["invalid_quotes"] += int(val.get("invalid_quotes", 0))
        summary["needs_review"] += int(bool(val.get("needs_review")))
        print(
            f"{response_path.name}: estándares={val['standards_count']}, "
            f"exactas={val.get('exact_quotes', 0)}, espacios={val.get('canonicalized_quotes', 0)}, "
            f"OCR-espacios={val.get('ocr_spacing_canonicalized_quotes', 0)}, "
            f"OCR-fuzzy={val.get('fuzzy_ocr_canonicalized_quotes', 0)}, inválidas={val.get('invalid_quotes', 0)}"
        )

    (output / "resumen_validacion.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if summary["format_errors"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
