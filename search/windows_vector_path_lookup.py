from __future__ import annotations

from functools import lru_cache
from pathlib import Path
import sqlite3
import sys
from threading import RLock

from config.settings import SETTINGS
from search.vector_store import VectorStore


_PATCHED = False
_PATCH_LOCK = RLock()


@lru_cache(maxsize=8192)
def _resolve_path_cached(path_value: str, catalog_path: str) -> str:
    """Resolve a Qdrant path with an O(1) active-path fast path.

    Most Qdrant payloads already contain the current document path.  The
    previous implementation nevertheless scanned document_locations for every
    returned fragment.  On large Windows catalogs that turns one vector search
    into many expensive SQLite lookups.  Check the documents primary key first
    and only use historical indirection when the stored path is no longer
    active.
    """
    try:
        with sqlite3.connect(catalog_path, timeout=5) as connection:
            connection.execute("PRAGMA busy_timeout = 5000")

            current = connection.execute(
                """
                SELECT path
                FROM documents
                WHERE path = ?
                  AND is_deleted = 0
                LIMIT 1
                """,
                (path_value,),
            ).fetchone()
            if current and current[0]:
                return str(current[0])

            relocated = connection.execute(
                """
                SELECT current_location.path
                FROM document_locations AS historical
                JOIN document_locations AS current_location
                  ON current_location.content_hash = historical.content_hash
                 AND current_location.is_current <> 0
                JOIN documents AS d
                  ON d.path = current_location.path
                 AND d.is_deleted = 0
                WHERE historical.path = ?
                ORDER BY current_location.last_seen_at DESC
                LIMIT 1
                """,
                (path_value,),
            ).fetchone()
            if relocated and relocated[0]:
                return str(relocated[0])
    except sqlite3.Error:
        pass

    return path_value


def _ensure_historical_path_index(catalog_path: str | Path) -> None:
    """Add the missing index used by historical-path indirection.

    document_locations has PRIMARY KEY(content_hash, path), which cannot serve
    WHERE historical.path = ? efficiently because path is the second column.
    Creating this index is idempotent and does not alter document contents.
    """
    with sqlite3.connect(str(catalog_path), timeout=30) as connection:
        connection.execute("PRAGMA busy_timeout = 30000")
        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_document_locations_path
            ON document_locations(path)
            """
        )
        connection.commit()


def clear_vector_path_lookup_cache() -> None:
    _resolve_path_cached.cache_clear()


def install_windows_vector_path_lookup() -> bool:
    """Install the Windows-only fast path for Qdrant result path resolution."""
    global _PATCHED

    if sys.platform != "win32":
        return False

    with _PATCH_LOCK:
        if _PATCHED:
            return True

        _ensure_historical_path_index(SETTINGS.catalog_path)

        original_relocate_document = VectorStore.relocate_document
        original_relocate_documents = VectorStore.relocate_documents

        def fast_resolve_current_document_path(
            self: VectorStore,
            stored_path: str | Path,
        ) -> Path:
            del self
            path_value = str(stored_path)
            resolved = _resolve_path_cached(
                path_value,
                str(SETTINGS.catalog_path),
            )
            return Path(resolved)

        def relocate_document_and_clear(self: VectorStore, *args, **kwargs):
            result = original_relocate_document(self, *args, **kwargs)
            if result:
                clear_vector_path_lookup_cache()
            return result

        def relocate_documents_and_clear(self: VectorStore, *args, **kwargs):
            result = original_relocate_documents(self, *args, **kwargs)
            if result:
                clear_vector_path_lookup_cache()
            return result

        VectorStore._resolve_current_document_path = (
            fast_resolve_current_document_path
        )
        VectorStore.relocate_document = relocate_document_and_clear
        VectorStore.relocate_documents = relocate_documents_and_clear

        _PATCHED = True
        return True
