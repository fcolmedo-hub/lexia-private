from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

# Permite ejecutar este archivo directamente con:
#   python tools\exportar_estandares_piloto.py
# agregando la raíz del repositorio al path de importación.
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from config.settings import SETTINGS


DEFAULT_PATHS_FILE = (
    Path("runtime") / "standards_pilot" / "seleccion_50.txt"
)


@dataclass(frozen=True)
class ExportedDocument:
    path: str
    name: str
    metadata: dict
    total_pages: int | None
    fragments: list[dict]


def _load_metadata(raw: str | None) -> dict:
    try:
        value = json.loads(raw or "{}")
    except Exception:
        return {}
    return value if isinstance(value, dict) else {}


def _connect(catalog_path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(catalog_path, timeout=30)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA busy_timeout = 30000")
    connection.execute("PRAGMA query_only = ON")
    return connection


def _normalize_path(value: str) -> str:
    return str(Path(value.strip()).resolve())


def _load_requested_paths(paths_file: Path) -> list[str]:
    values: list[str] = []
    seen: set[str] = set()

    for raw in paths_file.read_text(encoding="utf-8-sig").splitlines():
        value = raw.strip().strip('"')
        if not value or value.startswith("#"):
            continue

        normalized = _normalize_path(value)
        key = normalized.casefold()
        if key in seen:
            continue
        seen.add(key)
        values.append(normalized)

    return values


def _select_documents(
    connection: sqlite3.Connection,
    requested_paths: list[str],
) -> list[sqlite3.Row]:
    if not requested_paths:
        return []

    # SQLite no garantiza que IN conserve el orden de la lista. Recuperamos
    # los documentos y luego reordenamos exactamente como seleccion_50.txt.
    placeholders = ",".join("?" for _ in requested_paths)
    rows = connection.execute(
        f"""
        SELECT d.path, d.name, d.metadata_json, d.total_pages,
               COUNT(f.fragment_index) AS fragment_count
        FROM documents d
        JOIN fragments f ON f.document_path = d.path
        WHERE COALESCE(d.is_deleted, 0) = 0
          AND d.category = 'Jurisprudencia'
          AND d.path IN ({placeholders})
        GROUP BY d.path, d.name, d.metadata_json, d.total_pages
        HAVING COUNT(f.fragment_index) > 0
        """,
        requested_paths,
    ).fetchall()

    by_path = {str(row["path"]).casefold(): row for row in rows}
    ordered: list[sqlite3.Row] = []
    for path in requested_paths:
        row = by_path.get(path.casefold())
        if row is not None:
            ordered.append(row)
    return ordered


def _load_fragments(
    connection: sqlite3.Connection,
    document_path: str,
) -> list[dict]:
    rows = connection.execute(
        """
        SELECT fragment_index, text_content, start_char, end_char,
               page_start, page_end
        FROM fragments
        WHERE document_path = ?
        ORDER BY fragment_index ASC
        """,
        (document_path,),
    ).fetchall()

    fragments: list[dict] = []
    for row in rows:
        fragment_index = int(row["fragment_index"])
        fragments.append(
            {
                "chunk_id": f"{document_path}::{fragment_index}",
                "fragment_index": fragment_index,
                "page_start": row["page_start"],
                "page_end": row["page_end"],
                "start_char": int(row["start_char"]),
                "end_char": int(row["end_char"]),
                "text": str(row["text_content"] or ""),
            }
        )
    return fragments


def export_documents(
    catalog_path: Path,
    requested_paths: list[str],
) -> tuple[list[ExportedDocument], list[str]]:
    with _connect(catalog_path) as connection:
        rows = _select_documents(connection, requested_paths)
        result: list[ExportedDocument] = []
        found: set[str] = set()

        for row in rows:
            path = str(row["path"])
            found.add(path.casefold())
            result.append(
                ExportedDocument(
                    path=path,
                    name=str(row["name"]),
                    metadata=_load_metadata(row["metadata_json"]),
                    total_pages=(
                        int(row["total_pages"])
                        if row["total_pages"] is not None
                        else None
                    ),
                    fragments=_load_fragments(connection, path),
                )
            )

        missing = [
            path for path in requested_paths if path.casefold() not in found
        ]
        return result, missing


def _render_document_for_ai(document: ExportedDocument) -> str:
    lines = [
        f"DOCUMENTO: {document.name}",
        f"RUTA_INTERNA: {document.path}",
        f"PAGINAS_DECLARADAS: {document.total_pages}",
        "METADATOS: " + json.dumps(document.metadata, ensure_ascii=False),
        "",
        "FRAGMENTOS EN ORDEN DOCUMENTAL:",
    ]

    for fragment in document.fragments:
        lines.extend(
            [
                "",
                (
                    f"[CHUNK {fragment['chunk_id']} | "
                    f"fragment_index={fragment['fragment_index']} | "
                    f"paginas={fragment['page_start']}-{fragment['page_end']}]"
                ),
                fragment["text"],
            ]
        )

    return "\n".join(lines).strip() + "\n"


def _iter_jsonl(rows: Iterable[dict]) -> Iterable[str]:
    for row in rows:
        yield json.dumps(row, ensure_ascii=False, separators=(",", ":"))


def write_export(
    documents: list[ExportedDocument],
    prompt_template: str,
    output_dir: Path,
    source_paths_file: Path,
) -> dict[str, int | str]:
    output_dir.mkdir(parents=True, exist_ok=True)

    documents_path = output_dir / "fallos.jsonl"
    prompts_path = output_dir / "prompts.jsonl"
    manifest_path = output_dir / "manifest.json"

    document_rows = []
    prompt_rows = []
    total_fragments = 0
    total_chars = 0

    for position, document in enumerate(documents, start=1):
        total_fragments += len(document.fragments)
        document_text = _render_document_for_ai(document)
        total_chars += len(document_text)

        document_rows.append(
            {
                "pilot_id": position,
                "document_path": document.path,
                "document_name": document.name,
                "total_pages": document.total_pages,
                "metadata": document.metadata,
                "fragments": document.fragments,
            }
        )
        prompt_rows.append(
            {
                "pilot_id": position,
                "document_path": document.path,
                "document_name": document.name,
                "prompt": prompt_template.rstrip()
                + "\n\n"
                + document_text,
            }
        )

    documents_path.write_text(
        "\n".join(_iter_jsonl(document_rows)) + ("\n" if document_rows else ""),
        encoding="utf-8",
    )
    prompts_path.write_text(
        "\n".join(_iter_jsonl(prompt_rows)) + ("\n" if prompt_rows else ""),
        encoding="utf-8",
    )

    manifest = {
        "documents": len(documents),
        "fragments": total_fragments,
        "characters_in_ai_documents": total_chars,
        "selection_file": str(source_paths_file.resolve()),
        "documents_file": documents_path.name,
        "prompts_file": prompts_path.name,
        "purpose": "Piloto controlado de extracción de estándares jurídicos",
        "note": (
            "No llama a ninguna API. Exporta exclusivamente los documentos "
            "enumerados en seleccion_50.txt, en ese mismo orden, usando los "
            "fragmentos ya indexados en LexIA."
        ),
    }
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Exporta exclusivamente los fallos listados en seleccion_50.txt y "
            "todos sus fragmentos ya indexados en LexIA."
        )
    )
    parser.add_argument(
        "--catalog",
        type=Path,
        default=Path(SETTINGS.catalog_path),
        help="Ruta al catálogo SQLite de LexIA.",
    )
    parser.add_argument(
        "--paths-file",
        type=Path,
        default=DEFAULT_PATHS_FILE,
        help=(
            "TXT con una ruta de documento por línea. Por defecto: "
            "runtime/standards_pilot/seleccion_50.txt"
        ),
    )
    parser.add_argument(
        "--prompt",
        type=Path,
        default=(
            Path(__file__).resolve().parents[1]
            / "prompt"
            / "standards_extraction_v1.txt"
        ),
        help="Prompt maestro de extracción.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("runtime") / "standards_pilot" / "export_50",
        help="Directorio de salida.",
    )
    args = parser.parse_args()

    if not args.catalog.exists():
        parser.error(f"No existe el catálogo: {args.catalog}")
    if not args.prompt.exists():
        parser.error(f"No existe el prompt: {args.prompt}")
    if not args.paths_file.exists():
        parser.error(
            "No existe el archivo de selección: "
            f"{args.paths_file}. Cree seleccion_50.txt con una ruta por línea."
        )

    requested_paths = _load_requested_paths(args.paths_file)
    if not requested_paths:
        parser.error(f"La lista está vacía: {args.paths_file}")

    documents, missing = export_documents(
        catalog_path=args.catalog,
        requested_paths=requested_paths,
    )

    if missing:
        print("ERROR: algunos archivos de la selección no están indexados como Jurisprudencia")
        print("o no tienen fragmentos en el catálogo de LexIA:")
        for path in missing:
            print(f"  - {path}")
        print(f"Coincidencias: {len(documents)}/{len(requested_paths)}")
        print("No se generó la exportación para evitar un piloto incompleto.")
        return 3

    prompt_template = args.prompt.read_text(encoding="utf-8")
    manifest = write_export(
        documents,
        prompt_template,
        args.output,
        args.paths_file,
    )

    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    print(f"Exportación lista en: {args.output.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
