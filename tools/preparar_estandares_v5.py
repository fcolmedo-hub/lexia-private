from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

from preparar_estandares_v2 import compact_metadata, dump_jsonl, load_jsonl

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE = REPO_ROOT / "runtime" / "standards_pilot" / "export_50" / "fallos.jsonl"
DEFAULT_PROMPT = REPO_ROOT / "prompt" / "standards_extraction_v5.txt"
DEFAULT_OUTPUT = REPO_ROOT / "runtime" / "standards_pilot" / "export_50_v5"

MIN_UNIT = 120
TARGET_UNIT = 420
MAX_UNIT = 760


def _candidate_boundaries(text: str) -> list[int]:
    boundaries = {0, len(text)}
    # Cortes naturales: fin de oración seguido de espacio, o saltos de párrafo.
    for m in re.finditer(r"(?<=[.!?;:])\s+|\n{2,}", text):
        boundaries.add(m.end())
    return sorted(boundaries)


def split_exact_units(text: str) -> list[tuple[int, int, str]]:
    """Particiona todo el chunk en spans contiguos sin alterar ni perder caracteres."""
    if not text:
        return []
    candidates = _candidate_boundaries(text)
    units: list[tuple[int, int, str]] = []
    start = 0
    n = len(text)

    while start < n:
        if n - start <= MAX_UNIT:
            end = n
        else:
            min_end = min(n, start + MIN_UNIT)
            target_end = min(n, start + TARGET_UNIT)
            max_end = min(n, start + MAX_UNIT)
            viable = [b for b in candidates if min_end <= b <= max_end]
            if viable:
                # Preferir el corte natural más cercano al tamaño objetivo.
                end = min(viable, key=lambda b: (abs(b - target_end), b))
            else:
                # Último recurso: cortar en whitespace cercano al máximo.
                window = text[start:max_end]
                ws_positions = [m.start() for m in re.finditer(r"\s+", window)]
                usable = [p for p in ws_positions if p >= MIN_UNIT]
                end = start + (usable[-1] if usable else MAX_UNIT)
                if end <= start:
                    end = max_end
        if end <= start:
            end = min(n, start + MAX_UNIT)
        units.append((start, end, text[start:end]))
        start = end

    assert "".join(unit_text for _, _, unit_text in units) == text
    return units


def prepare_document_v5(row: dict[str, Any]) -> tuple[dict[str, Any], str]:
    fragments = row.get("fragments") if isinstance(row.get("fragments"), list) else []
    mapped_fragments: list[dict[str, Any]] = []
    rendered: list[str] = [f"DOC: {row.get('document_name', '')}"]
    total_pages = row.get("total_pages")
    if total_pages is not None:
        rendered.append(f"PAGES: {total_pages}")
    metadata = compact_metadata(row.get("metadata"))
    if metadata:
        rendered.append("META:" + json.dumps(metadata, ensure_ascii=False, separators=(",", ":")))
    rendered.append("UNITS:")

    for chunk_pos, fragment in enumerate(fragments, start=1):
        if not isinstance(fragment, dict):
            continue
        chunk_id = f"C{chunk_pos:04d}"
        source_text = str(fragment.get("text") or "")
        page_start = fragment.get("page_start")
        page_end = fragment.get("page_end")
        units: list[dict[str, Any]] = []
        for unit_pos, (start, end, unit_text) in enumerate(split_exact_units(source_text), start=1):
            unit_id = f"{chunk_id}-U{unit_pos:03d}"
            units.append({
                "unit_id": unit_id,
                "unit_index": unit_pos,
                "start_offset": start,
                "end_offset": end,
                "text": unit_text,
            })
            rendered.extend((f"[{unit_id}]", unit_text))

        mapped_fragments.append({
            "chunk_id": chunk_id,
            "original_chunk_id": fragment.get("chunk_id"),
            "fragment_index": fragment.get("fragment_index"),
            "page_start": page_start,
            "page_end": page_end,
            "start_char": fragment.get("start_char"),
            "end_char": fragment.get("end_char"),
            "text": source_text,
            "units": units,
        })

    prepared = {
        "pilot_id": row.get("pilot_id"),
        "document_path": row.get("document_path"),
        "document_name": row.get("document_name"),
        "total_pages": total_pages,
        "metadata": row.get("metadata") if isinstance(row.get("metadata"), dict) else {},
        "fragments": mapped_fragments,
    }
    return prepared, "\n".join(rendered).strip() + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Prepara v5 con IDs deterministas de unidades y texto jurídico íntegro.")
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--prompt", type=Path, default=DEFAULT_PROMPT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    if not args.source.exists():
        parser.error(f"No existe la fuente: {args.source}")
    if not args.prompt.exists():
        parser.error(f"No existe el prompt v5: {args.prompt}")

    source_rows = load_jsonl(args.source)
    prompt_template = args.prompt.read_text(encoding="utf-8").rstrip()
    args.output.mkdir(parents=True, exist_ok=True)

    prepared_rows: list[dict[str, Any]] = []
    prompt_rows: list[dict[str, Any]] = []
    source_chars = 0
    ai_chars = 0
    fragments_total = 0
    units_total = 0

    for row in source_rows:
        prepared, document_text = prepare_document_v5(row)
        prepared_rows.append(prepared)
        fragments_total += len(prepared["fragments"])
        units_total += sum(len(f.get("units", [])) for f in prepared["fragments"])
        source_chars += sum(len(str(f.get("text") or "")) for f in row.get("fragments", []) if isinstance(f, dict))
        full_prompt = prompt_template + "\n\n" + document_text
        ai_chars += len(full_prompt)
        prompt_rows.append({
            "pilot_id": prepared.get("pilot_id"),
            "document_path": prepared.get("document_path"),
            "document_name": prepared.get("document_name"),
            "prompt": full_prompt,
        })

    dump_jsonl(args.output / "fallos.jsonl", prepared_rows)
    dump_jsonl(args.output / "prompts.jsonl", prompt_rows)
    manifest = {
        "version": 5,
        "documents": len(prepared_rows),
        "fragments": fragments_total,
        "units": units_total,
        "source_text_characters": source_chars,
        "characters_sent_to_ai_including_prompt": ai_chars,
        "full_legal_text_preserved": True,
        "structured_outputs_expected": True,
        "evidence_mode": "deterministic_unit_ids",
        "anchors_removed": True,
        "fuzzy_matching_required": False,
        "note": "Mantiene la extracción jurídica v4.1; sólo reemplaza anclas por IDs deterministas de unidades. Python resuelve los IDs directamente al texto original.",
    }
    (args.output / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    print(f"Preparación v5 lista en: {args.output.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
