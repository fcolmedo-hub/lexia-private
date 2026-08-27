from __future__ import annotations

import os
import sqlite3
from pathlib import Path

# Fuerza qdrant-client local/embebido para esta reconstrucción experimental.
os.environ["LEXIA_QDRANT_MODE"] = "local"

from config.settings import SETTINGS
from services.application import LexIAApplication


def reset_vector_hashes() -> int:
    with sqlite3.connect(SETTINGS.catalog_path) as connection:
        row = connection.execute(
            """
            SELECT COUNT(*)
            FROM documents
            WHERE is_deleted = 0
              AND extraction_error IS NULL
              AND duplicate_of IS NULL
            """
        ).fetchone()
        total = int(row[0] or 0)
        connection.execute(
            """
            UPDATE documents
            SET vector_indexed_hash = NULL
            WHERE is_deleted = 0
              AND extraction_error IS NULL
              AND duplicate_of IS NULL
            """
        )
    return total


def main() -> int:
    SETTINGS.vector_path.mkdir(parents=True, exist_ok=True)
    total = reset_vector_hashes()
    print(f"Qdrant local: documentos marcados para reindexar: {total}", flush=True)
    print(f"Qdrant local: storage: {Path(SETTINGS.vector_path).resolve()}", flush=True)

    app = LexIAApplication()

    def progress(done: int, total_work: int, current: str) -> None:
        print(f"[{done}/{total_work}] {current}", flush=True)

    result = app.indexer.run(progress_callback=progress)
    status = app.vector_store.status()
    print("\nResultado:", flush=True)
    print(f"  documentos_indexados: {result.documents_indexed}", flush=True)
    print(f"  fragmentos_indexados: {result.fragments_indexed}", flush=True)
    print(f"  cancelado: {result.cancelled}", flush=True)
    print(f"  modo_vectorial: {status.get('mode')}", flush=True)
    print(f"  puntos_qdrant: {status.get('points')}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
