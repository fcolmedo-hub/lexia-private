from __future__ import annotations

import argparse
import os
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Fuerza qdrant-client local/embebido para esta prueba experimental.
os.environ["LEXIA_QDRANT_MODE"] = "local"

from config.settings import SETTINGS
from services.application import LexIAApplication


def count_pending_documents() -> int:
    with sqlite3.connect(SETTINGS.catalog_path) as connection:
        row = connection.execute(
            """
            SELECT COUNT(*)
            FROM documents
            WHERE is_deleted = 0
              AND extraction_error IS NULL
              AND duplicate_of IS NULL
              AND content_hash != COALESCE(vector_indexed_hash, '')
            """
        ).fetchone()
    return int(row[0] or 0)


def reset_vector_hashes_for_full_rebuild() -> int:
    """Uso deliberadamente peligroso: invalida el estado vectorial global.

    Sólo debe ejecutarse si se quiere reindexar toda la base. Para pruebas de
    Qdrant local no se usa por defecto, porque el catálogo comparte el campo
    vector_indexed_hash con el modo Docker/server.
    """
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
    parser = argparse.ArgumentParser(
        description="Prueba experimental de Qdrant local para LexIA en Windows."
    )
    parser.add_argument(
        "--force-all",
        action="store_true",
        help=(
            "Reindexa toda la base. Invalida vector_indexed_hash global; "
            "no usar para una prueba rápida."
        ),
    )
    args = parser.parse_args()

    SETTINGS.vector_path.mkdir(parents=True, exist_ok=True)

    if args.force_all:
        total = reset_vector_hashes_for_full_rebuild()
        print(
            "Qdrant local: REINDEXADO TOTAL solicitado explícitamente.",
            flush=True,
        )
        print(f"Qdrant local: documentos marcados para reindexar: {total}", flush=True)
    else:
        total = count_pending_documents()
        print(
            "Qdrant local: modo seguro. No se invalida el índice Docker/server.",
            flush=True,
        )
        print(
            "Qdrant local: documentos pendientes según catálogo compartido: "
            f"{total}",
            flush=True,
        )
        if total == 0:
            print(
                "No hay documentos pendientes. Para reconstruir todo usar --force-all, "
                "pero no lo hagas salvo que aceptes una reindexación completa.",
                flush=True,
            )
            return 0

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
