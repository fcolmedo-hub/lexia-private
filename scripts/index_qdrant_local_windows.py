from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Indexador local seguro: no usa Docker y no modifica vector_indexed_hash.
os.environ["LEXIA_QDRANT_MODE"] = "local"

from config.settings import SETTINGS
from models.document import Document
from models.fragment import Fragment
from search.embedding_service import EmbeddingService
from search.vector_store import VectorStore


DEFAULT_BATCH_DOCS = 8
DEFAULT_LIMIT_DOCS = 1000


def state_db_path() -> Path:
    path = Path(SETTINGS.runtime_path) / "qdrant_local_index_state.sqlite"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def connect_state() -> sqlite3.Connection:
    con = sqlite3.connect(state_db_path(), timeout=30)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA busy_timeout = 30000")
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS indexed_docs (
            path TEXT PRIMARY KEY,
            content_hash TEXT NOT NULL,
            fragment_count INTEGER NOT NULL,
            indexed_at TEXT NOT NULL
        )
        """
    )
    con.commit()
    return con


def reset_local_index(vector_store: VectorStore, state: sqlite3.Connection) -> None:
    if vector_store.client.collection_exists(vector_store.collection_name):
        vector_store.client.delete_collection(vector_store.collection_name)
    vector_store._ensure_collection()
    state.execute("DELETE FROM indexed_docs")
    state.commit()


def count_catalog_docs() -> int:
    with sqlite3.connect(SETTINGS.catalog_path) as con:
        row = con.execute(
            """
            SELECT COUNT(*)
            FROM documents d
            WHERE d.is_deleted = 0
              AND d.extraction_error IS NULL
              AND d.duplicate_of IS NULL
              AND EXISTS (
                  SELECT 1
                  FROM fragments f
                  WHERE f.document_path = d.path
              )
            """
        ).fetchone()
    return int(row[0] or 0)


def count_indexed_state(state: sqlite3.Connection) -> int:
    row = state.execute("SELECT COUNT(*) FROM indexed_docs").fetchone()
    return int(row[0] or 0)


def load_next_documents(
    remaining_limit: int,
    batch_docs: int,
) -> list[Document]:
    """Carga un lote de documentos pendientes para el índice local.

    La tabla de estado local es independiente del catalogo principal. El campo
    vector_indexed_hash no se lee ni se modifica.
    """
    limit = max(1, min(int(remaining_limit), int(batch_docs)))
    catalog = sqlite3.connect(SETTINGS.catalog_path, timeout=30)
    catalog.row_factory = sqlite3.Row
    try:
        catalog.execute("PRAGMA busy_timeout = 30000")
        catalog.execute("ATTACH DATABASE ? AS local_state", (str(state_db_path()),))
        rows = catalog.execute(
            """
            SELECT
                d.path,
                d.name,
                d.category,
                d.extension,
                d.size,
                d.modified_ns,
                d.content_hash,
                d.text_content,
                d.extraction_error,
                d.metadata_json,
                d.extraction_method,
                d.ocr_pages,
                d.total_pages,
                d.duplicate_of
            FROM documents d
            WHERE d.is_deleted = 0
              AND d.extraction_error IS NULL
              AND d.duplicate_of IS NULL
              AND EXISTS (
                  SELECT 1
                  FROM fragments f
                  WHERE f.document_path = d.path
              )
              AND NOT EXISTS (
                  SELECT 1
                  FROM local_state.indexed_docs s
                  WHERE s.path = d.path
                    AND s.content_hash = d.content_hash
              )
            ORDER BY d.path COLLATE NOCASE
            LIMIT ?
            """,
            (limit,),
        ).fetchall()

        documents: list[Document] = []
        for row in rows:
            try:
                metadata = json.loads(row["metadata_json"] or "{}")
            except Exception:
                metadata = {}
            if not isinstance(metadata, dict):
                metadata = {}

            path = Path(row["path"])
            document = Document(
                name=row["name"],
                path=path,
                category=row["category"] or "Sin categoría",
                extension=row["extension"] or "",
                size=int(row["size"] or 0),
                modified_ns=int(row["modified_ns"] or 0),
                content_hash=row["content_hash"] or "",
                text=row["text_content"] or "",
                extraction_error=row["extraction_error"],
                metadata=metadata,
                extraction_method=row["extraction_method"] or "native",
                ocr_pages=int(row["ocr_pages"] or 0),
                total_pages=row["total_pages"],
                duplicate_of=row["duplicate_of"],
            )
            frag_rows = catalog.execute(
                """
                SELECT
                    fragment_index,
                    category,
                    text_content,
                    start_char,
                    end_char,
                    page_start,
                    page_end
                FROM fragments
                WHERE document_path = ?
                ORDER BY fragment_index
                """,
                (row["path"],),
            ).fetchall()
            document.fragments = [
                Fragment(
                    document_name=document.name,
                    document_path=document.path,
                    category=fr["category"] or document.category,
                    index=int(fr["fragment_index"]),
                    text=fr["text_content"] or "",
                    start_char=int(fr["start_char"] or 0),
                    end_char=int(fr["end_char"] or 0),
                    page_start=fr["page_start"],
                    page_end=fr["page_end"],
                )
                for fr in frag_rows
                if (fr["text_content"] or "").strip()
            ]
            if document.fragments:
                documents.append(document)
        return documents
    finally:
        try:
            catalog.execute("DETACH DATABASE local_state")
        except Exception:
            pass
        catalog.close()


def mark_indexed(state: sqlite3.Connection, documents: list[Document]) -> None:
    now = datetime.now().isoformat(timespec="seconds")
    state.executemany(
        """
        INSERT INTO indexed_docs(path, content_hash, fragment_count, indexed_at)
        VALUES(?, ?, ?, ?)
        ON CONFLICT(path) DO UPDATE SET
            content_hash = excluded.content_hash,
            fragment_count = excluded.fragment_count,
            indexed_at = excluded.indexed_at
        """,
        [
            (
                str(document.path),
                document.content_hash,
                len(document.fragments),
                now,
            )
            for document in documents
        ],
    )
    state.commit()


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Construye un índice Qdrant local seguro, sin Docker y sin tocar "
            "vector_indexed_hash."
        )
    )
    parser.add_argument("--limit-docs", type=int, default=DEFAULT_LIMIT_DOCS)
    parser.add_argument("--batch-docs", type=int, default=DEFAULT_BATCH_DOCS)
    parser.add_argument("--reset", action="store_true")
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--confirm-full", action="store_true")
    args = parser.parse_args()

    if args.all and not args.confirm_full:
        raise SystemExit(
            "Para indexar todo usá --all --confirm-full. "
            "Primero probá con --limit-docs 1000."
        )

    limit_docs = None if args.all else max(1, int(args.limit_docs))
    batch_docs = max(1, int(args.batch_docs))

    print("Qdrant local index: modo seguro", flush=True)
    print(f"Storage local: {Path(SETTINGS.vector_path).resolve()}", flush=True)
    print(f"Coleccion: {SETTINGS.collection_name}", flush=True)
    print("No modifica vector_indexed_hash ni el índice Docker/server.", flush=True)

    state = connect_state()
    vector_store = VectorStore(EmbeddingService())
    started = time.perf_counter()
    indexed_now_docs = 0
    indexed_now_fragments = 0

    try:
        if args.reset:
            print("Reset local solicitado: se borra sólo el índice local y su estado local.", flush=True)
            reset_local_index(vector_store, state)

        total_catalog = count_catalog_docs()
        already = count_indexed_state(state)
        target = total_catalog if args.all else min(int(limit_docs or 0), total_catalog)
        print(f"Documentos con fragmentos en catalogo: {total_catalog}", flush=True)
        print(f"Documentos ya registrados en estado local: {already}", flush=True)
        print(f"Objetivo de esta corrida: {target} documentos", flush=True)

        while indexed_now_docs < target:
            remaining = target - indexed_now_docs
            documents = load_next_documents(remaining, batch_docs)
            if not documents:
                break

            counts = vector_store.replace_documents_batch(documents, wait=True)
            mark_indexed(state, documents)

            batch_doc_count = len(documents)
            batch_fragment_count = sum(int(value or 0) for value in counts.values())
            indexed_now_docs += batch_doc_count
            indexed_now_fragments += batch_fragment_count
            elapsed = time.perf_counter() - started
            print(
                f"Indexados ahora: docs={indexed_now_docs} "
                f"frags={indexed_now_fragments} tiempo={elapsed:.1f}s",
                flush=True,
            )

        status = vector_store.status()
        elapsed = time.perf_counter() - started
        print("\nResultado índice local:", flush=True)
        print(f"  documentos_indexados_en_esta_corrida: {indexed_now_docs}", flush=True)
        print(f"  fragmentos_indexados_en_esta_corrida: {indexed_now_fragments}", flush=True)
        print(f"  puntos_qdrant_local: {status.get('points')}", flush=True)
        print(f"  tiempo_total: {elapsed:.1f}s", flush=True)
        print(f"  estado_local_sqlite: {state_db_path()}", flush=True)
        return 0
    finally:
        try:
            vector_store.client.close()
        except Exception:
            pass
        state.close()


if __name__ == "__main__":
    raise SystemExit(main())
