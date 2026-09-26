from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE = REPO_ROOT / "runtime" / "standards_pilot" / "export_50" / "fallos.jsonl"
DEFAULT_PROMPT = REPO_ROOT / "prompt" / "standards_extraction_v2.txt"
DEFAULT_OUTPUT = REPO_ROOT / "runtime" / "standards_pilot" / "export_50_v2"


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as fh:
        for lineno, raw in enumerate(fh, start=1):
            raw = raw.strip()
            if not raw:
                continue
            try:
                value = json.loads(raw)
            except json.JSONDecodeError as exc:
                raise RuntimeError(f"JSON inválido en {path}, línea {lineno}: {exc}") from exc
            if not isinstance(value, dict):
                raise RuntimeError(f"Registro no-objeto en {path}, línea {lineno}")
            rows.append(value)
    return rows


def dump_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.write_text(
        "\n".join(json.dumps(row, ensure_ascii=False, separators=(",", ":")) for row in rows)
        + ("\n" if rows else ""),
        encoding="utf-8",
    )


def compact_metadata(metadata: Any) -> dict[str, Any]:
    if not isinstance(metadata, dict):
        return {}
    # Sólo claves potencialmente útiles para atribución/contexto. No se manda la ruta física.
    preferred = (
        "court", "tribunal", "date", "fecha", "jurisdiction", "jurisdiccion",
        "document_type", "tipo_documento", "chamber", "sala",
    )
    result: dict[str, Any] = {}
    lower_map = {str(k).casefold(): k for k in metadata.keys()}
    for key in preferred:
        original = lower_map.get(key.casefold())
        if original is not None:
            value = metadata.get(original)
            if value not in (None, "", [], {}):
                result[str(original)] = value
    return result


def prepare_document(row: dict[str, Any]) -> tuple[dict[str, Any], str]:
    fragments = row.get("fragments")
    if not isinstance(fragments, list):
        fragments = []

    mapped_fragments: list[dict[str, Any]] = []
    rendered: list[str] = [f"DOC: {row.get('document_name', '')}"]
    total_pages = row.get("total_pages")
    if total_pages is not None:
        rendered.append(f"PAGES: {total_pages}")

    metadata = compact_metadata(row.get("metadata"))
    if metadata:
        rendered.append("META:" + json.dumps(metadata, ensure_ascii=False, separators=(",", ":")))

    rendered.append("CHUNKS:")
    for pos, fragment in enumerate(fragments, start=1):
        if not isinstance(fragment, dict):
            continue
        short_id = f"C{pos:04d}"
        page_start = fragment.get("page_start")
        page_end = fragment.get("page_end")
        text = str(fragment.get("text") or "")
        if page_start is None and page_end is None:
            header = f"[{short_id}]"
        elif page_start == page_end or page_end is None:
            header = f"[{short_id}|p{page_start}]"
        else:
            header = f"[{short_id}|p{page_start}-{page_end}]"
        rendered.extend((header, text))
        mapped_fragments.append(
            {
                "chunk_id": short_id,
                "original_chunk_id": fragment.get("chunk_id"),
                "fragment_index": fragment.get("fragment_index"),
                "page_start": page_start,
                "page_end": page_end,
                "start_char": fragment.get("start_char"),
                "end_char": fragment.get("end_char"),
                "text": text,
            }
        )

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
    parser = argparse.ArgumentParser(description="Prepara prompts v2 compactos sin perder contenido jurídico de los chunks.")
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--prompt", type=Path, default=DEFAULT_PROMPT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    if not args.source.exists():
        parser.error(f"No existe la fuente: {args.source}")
    if not args.prompt.exists():
        parser.error(f"No existe el prompt v2: {args.prompt}")

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
        # Cuenta aproximada del material previo comparable: texto + IDs originales/metadata.
        source_chars += sum(len(str(f.get("text") or "")) for f in row.get("fragments", []) if isinstance(f, dict))
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

    fallos_path = args.output / "fallos.jsonl"
    prompts_path = args.output / "prompts.jsonl"
    manifest_path = args.output / "manifest.json"
    dump_jsonl(fallos_path, prepared_rows)
    dump_jsonl(prompts_path, prompt_rows)

    manifest = {
        "version": 2,
        "documents": len(prepared_rows),
        "fragments": fragments_total,
        "source_text_characters": source_chars,
        "characters_sent_to_ai_including_prompt": ai_chars,
        "short_chunk_ids": True,
        "full_document_path_sent_to_ai": False,
        "page_fields_removed_from_model_output": True,
        "identifier_generated_by_python": True,
        "note": "Mantiene íntegro el texto de todos los chunks; sólo compacta encabezados, IDs, metadatos e instrucciones.",
    }
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    print(f"Preparación v2 lista en: {args.output.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
