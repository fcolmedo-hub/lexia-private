from __future__ import annotations

import argparse
import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from config.settings import SETTINGS


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


def _load_requested_paths(paths_file: Path | None) -> list[str]:
    if paths_file is None:
        return []
    values: list[str] = []
    for raw in paths_file.read_text(encoding="utf-8").splitlines():
        value = raw.strip()
        if value and not value.startswith("#"):
            values.append(value)
    return values


def _select_documents(
    connection: sqlite3.Connection,
    limit: int,
    requested_paths: list[str],
) -> list[sqlite3.Row]:
    if requested_paths:
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
            ORDER BY d.path COLLATE NOCASE
            """,
            requested_paths,
        ).fetchall()
        return rows

    return connection.execute(
        """
        SELECT d.path, d.name, d.metadata_json, d.total_pages,
               COUNT(f.fragment_index) AS fragment_count
        FROM documents d
        JOIN fragments f ON f.document_path = d.path
        WHERE COALESCE(d.is_deleted, 0) = 0
          AND d.category = 'Jurisprudencia'
          AND LENGTH(TRIM(d.text_content)) >= 500
        GROUP BY d.path, d.name, d.metadata_json, d.total_pages
        HAVING COUNT(f.fragment_index) > 0
        ORDER BY d.path COLLATE NOCASE
        LIMIT ?
        """,
        (limit,),
    ).fetchall()


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
    limit: int,
    requested_paths: list[str] | None = None,
) -> list[ExportedDocument]:
    requested_paths = requested_paths or []
    with _connect(catalog_path) as connection:
        rows = _select_documents(connection, limit, requested_paths)
        result: list[ExportedDocument] = []
        for row in rows:
            path = str(row["path"])
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
        return result


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
        "documents_file": documents_path.name,
        "prompts_file": prompts_path.name,
        "purpose": "Piloto controlado de extracción de estándares jurídicos",
        "note": (
            "No llama a ninguna API. Sólo exporta, en modo lectura, los "
            "fragmentos ya indexados en LexIA y construye prompts listos para prueba."
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
            "Exporta fallos de Jurisprudencia y todos sus fragmentos ya "
            "indexados en LexIA para un piloto de extracción de estándares."
        )
    )
    parser.add_argument(
        "--catalog",
        type=Path,
        default=Path(SETTINGS.catalog_path),
        help="Ruta al catálogo SQLite de LexIA.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=50,
        help="Cantidad de fallos a exportar si no se usa --paths-file.",
    )
    parser.add_argument(
        "--paths-file",
        type=Path,
        default=None,
        help="TXT opcional con una ruta de documento por línea.",
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

    if args.limit < 1:
        parser.error("--limit debe ser mayor que cero")
    if not args.catalog.exists():
        parser.error(f"No existe el catálogo: {args.catalog}")
    if not args.prompt.exists():
        parser.error(f"No existe el prompt: {args.prompt}")

    requested_paths = _load_requested_paths(args.paths_file)
    documents = export_documents(
        catalog_path=args.catalog,
        limit=args.limit,
        requested_paths=requested_paths,
    )
    prompt_template = args.prompt.read_text(encoding="utf-8")
    manifest = write_export(documents, prompt_template, args.output)

    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    if not documents:
        print("No se encontraron fallos elegibles.")
        return 2

    print(f"Exportación lista en: {args.output.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
