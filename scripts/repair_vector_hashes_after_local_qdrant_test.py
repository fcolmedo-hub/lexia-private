from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from config.settings import SETTINGS


def main() -> int:
    catalog = Path(SETTINGS.catalog_path)
    if not catalog.exists():
        raise SystemExit(f"No existe el catálogo: {catalog}")

    with sqlite3.connect(catalog) as connection:
        row = connection.execute(
            """
            SELECT COUNT(*)
            FROM documents
            WHERE is_deleted = 0
              AND extraction_error IS NULL
              AND duplicate_of IS NULL
              AND COALESCE(vector_indexed_hash, '') = ''
            """
        ).fetchone()
        pending = int(row[0] or 0)

        connection.execute(
            """
            UPDATE documents
            SET vector_indexed_hash = content_hash
            WHERE is_deleted = 0
              AND extraction_error IS NULL
              AND duplicate_of IS NULL
              AND COALESCE(vector_indexed_hash, '') = ''
            """
        )

        fixed = int(connection.total_changes or 0)

    print(f"Catálogo: {catalog}")
    print(f"Documentos con vector_indexed_hash vacío antes: {pending}")
    print(f"Documentos reparados: {fixed}")
    print("Estado restaurado: el catálogo ya no pedirá reindexar toda la base.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
