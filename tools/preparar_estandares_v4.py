from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from tools.preparar_estandares_v2 import dump_jsonl, load_jsonl, prepare_document

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE = REPO_ROOT / "runtime" / "standards_pilot" / "export_50" / "fallos.jsonl"
DEFAULT_PROMPT = REPO_ROOT / "prompt" / "standards_extraction_v4.txt"
DEFAULT_OUTPUT = REPO_ROOT / "runtime" / "standards_pilot" / "export_50_v4"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Prepara prompts v4: mismo texto jurídico íntegro de v2, con evidencia por anclas."
    )
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--prompt", type=Path, default=DEFAULT_PROMPT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    if not args.source.exists():
        parser.error(f"No existe la fuente: {args.source}")
    if not args.prompt.exists():
        parser.error(f"No existe el prompt v4: {args.prompt}")

    source_rows = load_jsonl(args.source)
    prompt_template = args.prompt.read_text(encoding="utf-8").rstrip()
    args.output.mkdir(parents=True, exist_ok=True)

    prepared_rows: list[dict[str, Any]] = []
    prompt_rows: list[dict[str, Any]] = []
    source_chars = 0
    ai_chars = 0
    fragments_total = 0

    for row in source_rows:
        prepared, document_text = prepare_document(row)
        prepared_rows.append(prepared)
        fragments_total += len(prepared["fragments"])
        source_chars += sum(
            len(str(f.get("text") or ""))
            for f in row.get("fragments", [])
            if isinstance(f, dict)
        )
        full_prompt = prompt_template + "\n\n" + document_text
        ai_chars += len(full_prompt)
        prompt_rows.append(
            {
                "pilot_id": prepared.get("pilot_id"),
                "document_path": prepared.get("document_path"),
                "document_name": prepared.get("document_name"),
                "prompt": full_prompt,
            }
        )

    dump_jsonl(args.output / "fallos.jsonl", prepared_rows)
    dump_jsonl(args.output / "prompts.jsonl", prompt_rows)

    manifest = {
        "version": 4,
        "documents": len(prepared_rows),
        "fragments": fragments_total,
        "source_text_characters": source_chars,
        "characters_sent_to_ai_including_prompt": ai_chars,
        "full_legal_text_preserved": True,
        "short_chunk_ids": True,
        "structured_outputs_expected": True,
        "model_does_not_produce_final_quote": True,
        "python_reconstructs_literal_quote": True,
        "note": "Mantiene el texto jurídico completo de v2. La IA identifica regla y anclas; Python reconstruye la cita literal desde el chunk original.",
    }
    (args.output / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    print(f"Preparación v4 lista en: {args.output.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
