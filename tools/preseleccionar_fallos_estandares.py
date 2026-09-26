"""Preselección revisable de fallos indexados para la extracción V5."""
from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from config.settings import SETTINGS


def candidates(catalog: Path, standards_db: Path, contains: str, limit: int) -> list[str]:
    if not catalog.is_file():
        raise FileNotFoundError(f"No existe el catálogo: {catalog}")
    excluded: set[str] = set()
    if standards_db.is_file():
        with sqlite3.connect(standards_db) as connection:
            if connection.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='documents'"
            ).fetchone():
                excluded = {
                    str(row[0]).casefold()
                    for row in connection.execute(
                        "SELECT document_path FROM documents WHERE document_path IS NOT NULL"
                    )
                }

    result: list[str] = []
    with sqlite3.connect(f"file:{catalog.resolve()}?mode=ro", uri=True) as connection:
        connection.execute("PRAGMA query_only=ON")
        rows = connection.execute(
            """SELECT d.path FROM documents d
               WHERE d.category='Jurisprudencia' AND COALESCE(d.is_deleted,0)=0
                 AND instr(lower(d.path),lower(?))>0
                 AND EXISTS (SELECT 1 FROM fragments f
                             WHERE f.document_path=d.path AND length(trim(f.text_content))>0)
               ORDER BY d.path COLLATE NOCASE""",
            (contains,),
        )
        for (path,) in rows:
            if str(path).casefold() in excluded:
                continue
            result.append(str(path))
            if len(result) >= limit:
                break
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalog", type=Path, default=Path(SETTINGS.catalog_path))
    parser.add_argument("--db", type=Path, default=Path(SETTINGS.runtime_path) / "standards" / "standards.sqlite3")
    parser.add_argument("--path-contains", required=True, help="Parte de la ruta o carpeta que delimita el lote")
    parser.add_argument("--limit", type=int, default=250)
    parser.add_argument("--output", type=Path, required=True, help="TXT de rutas para revisar antes de prepare")
    args = parser.parse_args()
    if not args.path_contains.strip() or not 1 <= args.limit <= 250:
        parser.error("Indicá una carpeta y un límite de 1 a 250 fallos.")
    if args.output.exists():
        parser.error(f"El archivo ya existe; no se sobrescribe: {args.output}")
    try:
        paths = candidates(args.catalog, args.db, args.path_contains.strip(), args.limit)
    except (OSError, sqlite3.Error) as error:
        parser.exit(1, f"No se pudo leer el catálogo: {error}\n")
    if not paths:
        parser.exit(1, "No hay fallos indexados nuevos en esa carpeta.\n")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text("\n".join(paths) + "\n", encoding="utf-8")
    print(f"{len(paths)} fallos preseleccionados en {args.output}. Revisá el TXT antes de preparar el lote; no se llamó a la API.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
