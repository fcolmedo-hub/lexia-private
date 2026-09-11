import sqlite3

from search.windows_vector_path_lookup import (
    _ensure_historical_path_index,
    _resolve_path_cached,
    clear_vector_path_lookup_cache,
)


def _build_catalog(path):
    with sqlite3.connect(path) as connection:
        connection.executescript(
            """
            CREATE TABLE documents (
                path TEXT PRIMARY KEY,
                content_hash TEXT NOT NULL,
                is_deleted INTEGER NOT NULL DEFAULT 0
            );
            CREATE TABLE document_locations (
                content_hash TEXT NOT NULL,
                path TEXT NOT NULL,
                last_seen_at TEXT NOT NULL,
                is_current INTEGER NOT NULL DEFAULT 1,
                PRIMARY KEY (content_hash, path)
            );
            """
        )
        connection.execute(
            "INSERT INTO documents(path, content_hash, is_deleted) VALUES (?, ?, 0)",
            (r"D:\Biblioteca\actual.pdf", "hash-1"),
        )
        connection.executemany(
            """
            INSERT INTO document_locations(
                content_hash, path, last_seen_at, is_current
            ) VALUES (?, ?, ?, ?)
            """,
            [
                (
                    "hash-1",
                    r"D:\Biblioteca\viejo.pdf",
                    "2026-09-01 10:00:00",
                    0,
                ),
                (
                    "hash-1",
                    r"D:\Biblioteca\actual.pdf",
                    "2026-09-11 10:00:00",
                    1,
                ),
            ],
        )


def test_current_path_uses_direct_documents_lookup(tmp_path):
    catalog = tmp_path / "catalog.sqlite3"
    _build_catalog(catalog)
    clear_vector_path_lookup_cache()

    resolved = _resolve_path_cached(
        r"D:\Biblioteca\actual.pdf",
        str(catalog),
    )

    assert resolved == r"D:\Biblioteca\actual.pdf"


def test_historical_path_resolves_to_current_location(tmp_path):
    catalog = tmp_path / "catalog.sqlite3"
    _build_catalog(catalog)
    _ensure_historical_path_index(catalog)
    clear_vector_path_lookup_cache()

    resolved = _resolve_path_cached(
        r"D:\Biblioteca\viejo.pdf",
        str(catalog),
    )

    assert resolved == r"D:\Biblioteca\actual.pdf"

    with sqlite3.connect(catalog) as connection:
        indexes = {
            row[1]
            for row in connection.execute(
                "PRAGMA index_list(document_locations)"
            ).fetchall()
        }

    assert "idx_document_locations_path" in indexes
