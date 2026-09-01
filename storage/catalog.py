import json
import logging
from time import perf_counter
import os
import sqlite3
from pathlib import Path

from models.document import Document
from models.fragment import Fragment


def _relocated_metadata_json(raw_metadata, category):
    """Keep embedded metadata consistent with the catalog category."""
    try:
        metadata = json.loads(raw_metadata or "{}")
    except Exception:
        metadata = {}

    if not isinstance(metadata, dict):
        metadata = {}

    metadata["category"] = str(category or "")

    return json.dumps(
        metadata,
        ensure_ascii=False,
        separators=(",", ":"),
    )


class DocumentCatalog:
    def __init__(self, database_path: str | Path):
        self.database_path = Path(database_path)
        self.database_path.parent.mkdir(parents=True, exist_ok=True)

        # >>> LEXIA CATALOG RELOCATION TIMING PROBE LOGFIX 1.0.1
        self._relocation_probe_logger = logging.getLogger(
            "lexia.catalog.relocation_probe"
        )
        self._relocation_probe_logger.setLevel(logging.INFO)
        self._relocation_probe_logger.propagate = False

        probe_log_path = (
            self.database_path.parent
            / "catalog_relocation_probe.log"
        ).resolve()

        has_probe_handler = any(
            isinstance(handler, logging.FileHandler)
            and Path(getattr(handler, "baseFilename", "")).resolve()
            == probe_log_path
            for handler in self._relocation_probe_logger.handlers
        )

        if not has_probe_handler:
            probe_handler = logging.FileHandler(
                probe_log_path,
                encoding="utf-8",
            )
            probe_handler.setLevel(logging.INFO)
            probe_handler.setFormatter(
                logging.Formatter(
                    "%(asctime)s | %(levelname)s | %(message)s",
                    datefmt="%Y-%m-%d %H:%M:%S",
                )
            )
            self._relocation_probe_logger.addHandler(probe_handler)
        # <<< LEXIA CATALOG RELOCATION TIMING PROBE LOGFIX 1.0.1

        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(
            self.database_path,
            timeout=30,
        )
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA busy_timeout = 30000")
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA synchronous = NORMAL")
        return connection

    def _initialize(self) -> None:
        # >>> LEXIA SQLITE WAL PERFORMANCE & LOCKING FIX 1.0
        bootstrap = sqlite3.connect(
            self.database_path,
            timeout=30,
        )
        try:
            bootstrap.execute("PRAGMA busy_timeout = 30000")
            mode = bootstrap.execute(
                "PRAGMA journal_mode = WAL"
            ).fetchone()[0]
            if str(mode).lower() != "wal":
                raise RuntimeError(
                    f"No se pudo activar WAL; journal_mode={mode!r}"
                )
            bootstrap.execute("PRAGMA synchronous = NORMAL")
        finally:
            bootstrap.close()
        # <<< LEXIA SQLITE WAL PERFORMANCE & LOCKING FIX 1.0

        with self._connect() as connection:
            connection.executescript(
                '''
                CREATE TABLE IF NOT EXISTS documents (
                    path TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    category TEXT NOT NULL DEFAULT 'Sin categoría',
                    extension TEXT NOT NULL,
                    size INTEGER NOT NULL,
                    modified_ns INTEGER NOT NULL,
                    content_hash TEXT NOT NULL,
                    vector_indexed_hash TEXT,
                    text_content TEXT NOT NULL,
                    extraction_error TEXT,
                    metadata_json TEXT NOT NULL DEFAULT '{}',
                    extraction_method TEXT NOT NULL DEFAULT 'native',
                    ocr_pages INTEGER NOT NULL DEFAULT 0,
                    total_pages INTEGER,
                    duplicate_of TEXT,
                    is_deleted INTEGER NOT NULL DEFAULT 0,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS fragments (
                    document_path TEXT NOT NULL,
                    fragment_index INTEGER NOT NULL,
                    category TEXT NOT NULL DEFAULT 'Sin categoría',
                    text_content TEXT NOT NULL,
                    start_char INTEGER NOT NULL,
                    end_char INTEGER NOT NULL,
                    page_start INTEGER,
                    page_end INTEGER,
                    PRIMARY KEY (document_path, fragment_index),
                    FOREIGN KEY (document_path)
                        REFERENCES documents(path)
                        ON DELETE CASCADE
                );

                CREATE VIRTUAL TABLE IF NOT EXISTS fragments_fts
                USING fts5(
                    document_path UNINDEXED,
                    fragment_index UNINDEXED,
                    category UNINDEXED,
                    document_name UNINDEXED,
                    text_content,
                    tokenize = 'unicode61 remove_diacritics 2'
                );

                CREATE TABLE IF NOT EXISTS document_locations (
                    content_hash TEXT NOT NULL,
                    path TEXT NOT NULL,
                    first_seen_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    last_seen_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    is_current INTEGER NOT NULL DEFAULT 1,
                    PRIMARY KEY (content_hash, path)
                );

                CREATE TABLE IF NOT EXISTS vector_relocations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    content_hash TEXT NOT NULL,
                    old_path TEXT NOT NULL,
                    new_path TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'pending',
                    error TEXT,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    completed_at TEXT
                );

                CREATE INDEX IF NOT EXISTS
                    idx_documents_active_name
                ON documents(
                    name COLLATE NOCASE,
                    path COLLATE NOCASE
                )
                WHERE is_deleted = 0;

                CREATE INDEX IF NOT EXISTS
                    idx_documents_active_category_name
                ON documents(
                    category,
                    name COLLATE NOCASE,
                    path COLLATE NOCASE
                )
                WHERE is_deleted = 0;

                CREATE INDEX IF NOT EXISTS
                    idx_documents_active_updated
                ON documents(
                    updated_at DESC,
                    name COLLATE NOCASE
                )
                WHERE is_deleted = 0;

                CREATE INDEX IF NOT EXISTS
                    idx_documents_active_category_updated
                ON documents(
                    category,
                    updated_at DESC,
                    name COLLATE NOCASE
                )
                WHERE is_deleted = 0;

                CREATE INDEX IF NOT EXISTS
                    idx_documents_active_error_updated
                ON documents(updated_at DESC)
                WHERE is_deleted = 0
                  AND extraction_error IS NOT NULL
                  AND extraction_error != '';
                '''
            )

            self._ensure_column(
                connection,
                "documents",
                "metadata_json",
                "TEXT NOT NULL DEFAULT '{}'",
            )
            self._ensure_column(
                connection,
                "fragments",
                "page_start",
                "INTEGER",
            )
            self._ensure_column(
                connection,
                "fragments",
                "page_end",
                "INTEGER",
            )

            self._ensure_column(
                connection,
                "documents",
                "extraction_method",
                "TEXT NOT NULL DEFAULT 'native'",
            )
            self._ensure_column(
                connection,
                "documents",
                "ocr_pages",
                "INTEGER NOT NULL DEFAULT 0",
            )
            self._ensure_column(
                connection,
                "documents",
                "total_pages",
                "INTEGER",
            )
            self._ensure_column(
                connection,
                "documents",
                "duplicate_of",
                "TEXT",
            )
            # Existing catalogs did not preserve the first insertion time.  Keep
            # migrated rows NULL instead of pretending they were all added on
            # the migration day; new rows receive a real creation timestamp in
            # save().
            self._ensure_column(
                connection,
                "documents",
                "created_at",
                "TEXT",
            )

            connection.execute(
                """
                INSERT OR IGNORE INTO document_locations (
                    content_hash, path, is_current
                )
                SELECT content_hash, path,
                       CASE WHEN is_deleted = 0 THEN 1 ELSE 0 END
                FROM documents
                WHERE content_hash IS NOT NULL
                  AND content_hash != ''
                """
            )

    def _ensure_column(
        self,
        connection: sqlite3.Connection,
        table: str,
        column: str,
        definition: str,
    ) -> None:
        columns = {
            row["name"]
            for row in connection.execute(
                f"PRAGMA table_info({table})"
            ).fetchall()
        }

        if column not in columns:
            connection.execute(
                f"ALTER TABLE {table} ADD COLUMN {column} {definition}"
            )

    def get_hash(self, path: str | Path) -> str | None:
        resolved_path = str(Path(path).resolve())

        with self._connect() as connection:
            row = connection.execute(
                '''
                SELECT content_hash
                FROM documents
                WHERE path = ? AND is_deleted = 0
                ''',
                (resolved_path,),
            ).fetchone()

        return row["content_hash"] if row else None




    def get_file_state(
        self,
        path: str | Path,
    ) -> dict | None:
        resolved_path = str(Path(path).resolve())

        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT
                    path,
                    size,
                    modified_ns,
                    content_hash,
                    is_deleted,
                    duplicate_of,
                    text_content,
                    extraction_error,
                    extraction_method,
                    ocr_pages,
                    total_pages,
                    category
                FROM documents
                WHERE path = ?
                """,
                (resolved_path,),
            ).fetchone()

        return dict(row) if row else None

    def update_classification(
        self,
        path: str | Path,
        category: str,
        metadata: dict,
    ) -> None:
        resolved_path = str(Path(path).resolve())
        metadata_json = json.dumps(
            metadata,
            ensure_ascii=False,
        )

        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT name FROM documents
                WHERE path = ?
                """,
                (resolved_path,),
            ).fetchone()

            if not row:
                return

            connection.execute(
                """
                UPDATE documents
                SET category = ?,
                    metadata_json = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE path = ?
                """,
                (
                    category,
                    metadata_json,
                    resolved_path,
                ),
            )
            connection.execute(
                """
                UPDATE fragments
                SET category = ?
                WHERE document_path = ?
                """,
                (category, resolved_path),
            )
            connection.execute(
                """
                DELETE FROM fragments_fts
                WHERE document_path = ?
                """,
                (resolved_path,),
            )
            connection.execute(
                """
                INSERT INTO fragments_fts (
                    document_path,
                    fragment_index,
                    category,
                    document_name,
                    text_content
                )
                SELECT
                    document_path,
                    fragment_index,
                    category,
                    ?,
                    text_content
                FROM fragments
                WHERE document_path = ?
                """,
                (
                    row["name"],
                    resolved_path,
                ),
            )

    def repair_ocr_pending_categories(
        self,
        library_root: str | Path,
    ) -> int:
        """Restore structural categories for legacy OCR-pending entries."""
        from services.structural_category_policy import (
            classify_structural_path,
        )

        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT path, metadata_json
                FROM documents
                WHERE is_deleted = 0
                  AND LOWER(TRIM(category)) IN (
                      'ocr pendiente', 'ocr pendientes'
                  )
                """
            ).fetchall()

        repaired = 0
        for row in rows:
            try:
                structural = classify_structural_path(
                    row["path"],
                    library_root=library_root,
                )
            except (OSError, ValueError):
                continue
            try:
                metadata = json.loads(row["metadata_json"] or "{}")
            except (TypeError, ValueError):
                metadata = {}
            metadata["ocr_pending"] = True
            self.update_classification(
                row["path"],
                structural.category,
                metadata,
            )
            repaired += 1
        return repaired

    def find_relocation_candidate(
        self,
        content_hash: str,
        active_paths: set[str],
        exclude_path: str | Path,
    ) -> str | None:
        excluded = str(Path(exclude_path).resolve())
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT path
                FROM documents
                WHERE content_hash = ?
                  AND is_deleted = 0
                  AND path != ?
                ORDER BY
                    CASE WHEN duplicate_of IS NULL THEN 0 ELSE 1 END,
                    updated_at ASC
                """,
                (content_hash, excluded),
            ).fetchall()

        for row in rows:
            # La existencia física es la fuente de verdad. Esto evita
            # confundir una copia idéntica con un archivo movido durante
            # una sincronización dirigida a un solo archivo.
            if not Path(row["path"]).exists():
                return row["path"]
        return None

    def relocate_document(
        self,
        old_path: str | Path,
        document: Document,
    ) -> bool:
        old_resolved = str(Path(old_path).resolve())
        new_resolved = str(document.path.resolve())

        if old_resolved == new_resolved:
            return False

        # >>> LEXIA CATALOG RELOCATION TIMING PROBE 1.0
        _probe_total_started = perf_counter()
        _probe = {
            "connect_and_select": 0.0,
            "delete_new": 0.0,
            "insert_new_document": 0.0,
            "update_fragments": 0.0,
            "fts_refresh": 0.0,
            "duplicate_and_old_delete": 0.0,
            "locations_and_vector": 0.0,
            "commit_close": 0.0,
        }
        _probe_t0 = perf_counter()

        with self._connect() as connection:
            old = connection.execute(
                "SELECT * FROM documents WHERE path = ? AND is_deleted = 0",
                (old_resolved,),
            ).fetchone()
            _probe["connect_and_select"] += perf_counter() - _probe_t0

            if not old:
                return False

            _probe_t0 = perf_counter()
            connection.execute(
                "DELETE FROM fragments_fts WHERE document_path = ?",
                (new_resolved,),
            )
            connection.execute(
                "DELETE FROM documents WHERE path = ?",
                (new_resolved,),
            )
            _probe["delete_new"] += perf_counter() - _probe_t0

            _probe_t0 = perf_counter()
            connection.execute(
                """
                INSERT INTO documents (
                    path, name, category, extension, size, modified_ns,
                    content_hash, vector_indexed_hash, text_content,
                    extraction_error, metadata_json, extraction_method,
                    ocr_pages, total_pages, duplicate_of, is_deleted,
                    created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?,
                        CURRENT_TIMESTAMP)
                """,
                (
                    new_resolved,
                    document.name,
                    document.category,
                    document.extension,
                    document.size,
                    document.modified_ns,
                    old["content_hash"],
                    old["vector_indexed_hash"],
                    old["text_content"],
                    old["extraction_error"],
                    old["metadata_json"],
                    old["extraction_method"],
                    old["ocr_pages"],
                    old["total_pages"],
                    old["duplicate_of"],
                    old["created_at"],
                ),
            )
            _probe["insert_new_document"] += perf_counter() - _probe_t0

            _probe_t0 = perf_counter()
            connection.execute(
                """
                UPDATE fragments
                SET document_path = ?, category = ?
                WHERE document_path = ?
                """,
                (new_resolved, document.category, old_resolved),
            )
            _probe["update_fragments"] += perf_counter() - _probe_t0
            _probe_t0 = perf_counter()
            connection.execute(
                "DELETE FROM fragments_fts WHERE document_path = ?",
                (old_resolved,),
            )
            connection.execute(
                """
                INSERT INTO fragments_fts (
                    document_path, fragment_index, category,
                    document_name, text_content
                )
                SELECT ?, fragment_index, category, ?, text_content
                FROM fragments
                WHERE document_path = ?
                """,
                (new_resolved, document.name, new_resolved),
            )
            _probe["fts_refresh"] += perf_counter() - _probe_t0
            _probe_t0 = perf_counter()
            connection.execute(
                "UPDATE documents SET duplicate_of = ? WHERE duplicate_of = ?",
                (new_resolved, old_resolved),
            )
            connection.execute(
                "DELETE FROM documents WHERE path = ?",
                (old_resolved,),
            )
            _probe["duplicate_and_old_delete"] += perf_counter() - _probe_t0

            _probe_t0 = perf_counter()
            connection.execute(
                """
                INSERT INTO document_locations (
                    content_hash, path, is_current
                ) VALUES (?, ?, 0)
                ON CONFLICT(content_hash, path) DO UPDATE SET
                    is_current = 0,
                    last_seen_at = CURRENT_TIMESTAMP
                """,
                (old["content_hash"], old_resolved),
            )
            connection.execute(
                """
                INSERT INTO document_locations (
                    content_hash, path, is_current
                ) VALUES (?, ?, 1)
                ON CONFLICT(content_hash, path) DO UPDATE SET
                    is_current = 1,
                    last_seen_at = CURRENT_TIMESTAMP
                """,
                (old["content_hash"], new_resolved),
            )

            if old["duplicate_of"] is None and old["vector_indexed_hash"]:
                connection.execute(
                    """
                    INSERT INTO vector_relocations (
                        content_hash, old_path, new_path
                    ) VALUES (?, ?, ?)
                    """,
                    (old["content_hash"], old_resolved, new_resolved),
                )
            _probe["locations_and_vector"] += perf_counter() - _probe_t0

        _probe_total = perf_counter() - _probe_total_started
        _probe_measured = sum(_probe.values())
        _probe["commit_close"] = max(0.0, _probe_total - _probe_measured)
        self._relocation_probe_logger.info(
            "Catalog Relocation Timing Probe 1.0 | old=%s | new=%s | "
            "connect_select=%.4fs | delete_new=%.4fs | insert_new=%.4fs | "
            "update_fragments=%.4fs | fts_refresh=%.4fs | "
            "dup_old_delete=%.4fs | locations_vector=%.4fs | "
            "commit_close=%.4fs | total=%.4fs",
            old_resolved,
            new_resolved,
            _probe["connect_and_select"],
            _probe["delete_new"],
            _probe["insert_new_document"],
            _probe["update_fragments"],
            _probe["fts_refresh"],
            _probe["duplicate_and_old_delete"],
            _probe["locations_and_vector"],
            _probe["commit_close"],
            _probe_total,
        )
        return True


    # >>> LEXIA CATALOG RELOCATION BATCH 2.0
    def relocate_documents_batch(
        self,
        relocations: list[tuple[str | Path, Document]],
    ) -> dict:
        result = {
            "requested": len(relocations),
            "relocated": 0,
            "failed": [],
        }
        if not relocations:
            return result

        _probe_total_started = perf_counter()
        _probe = {
            "prepare": 0.0,
            "load_old_rows": 0.0,
            "delete_new_documents": 0.0,
            "insert_documents": 0.0,
            "update_fragments": 0.0,
            "fts_delete": 0.0,
            "fts_insert": 0.0,
            "duplicate_update": 0.0,
            "delete_old_documents": 0.0,
            "locations": 0.0,
            "vector_relocations": 0.0,
            "commit_close": 0.0,
        }

        _t0 = perf_counter()
        prepared = []
        for old_path, document in relocations:
            old_resolved = str(Path(old_path).resolve())
            new_resolved = str(document.path.resolve())
            if old_resolved == new_resolved:
                result["failed"].append({
                    "old_path": old_resolved,
                    "new_path": new_resolved,
                    "error": "same_path",
                })
                continue
            prepared.append((old_resolved, new_resolved, document))
        _probe["prepare"] = perf_counter() - _t0

        if not prepared:
            return result

        _commit_started = None

        try:
            with self._connect() as connection:
                connection.execute("BEGIN IMMEDIATE")

                connection.execute(
                    """
                    CREATE TEMP TABLE IF NOT EXISTS lexia_relocation_map (
                        old_path TEXT PRIMARY KEY,
                        new_path TEXT NOT NULL,
                        new_name TEXT NOT NULL,
                        new_category TEXT NOT NULL
                    )
                    """
                )
                connection.execute("DELETE FROM lexia_relocation_map")
                connection.executemany(
                    """
                    INSERT INTO lexia_relocation_map (
                        old_path, new_path, new_name, new_category
                    ) VALUES (?, ?, ?, ?)
                    """,
                    [
                        (
                            old_resolved,
                            new_resolved,
                            document.name,
                            document.category,
                        )
                        for old_resolved, new_resolved, document in prepared
                    ],
                )

                _t0 = perf_counter()
                old_rows = {
                    row["path"]: row
                    for row in connection.execute(
                        """
                        SELECT *
                        FROM documents
                        WHERE is_deleted = 0
                          AND path IN (
                            SELECT old_path FROM lexia_relocation_map
                          )
                        """
                    ).fetchall()
                }
                _probe["load_old_rows"] = perf_counter() - _t0

                valid = []
                for old_resolved, new_resolved, document in prepared:
                    if old_resolved not in old_rows:
                        result["failed"].append({
                            "old_path": old_resolved,
                            "new_path": new_resolved,
                            "error": "old_not_active",
                        })
                        continue
                    valid.append((old_resolved, new_resolved, document))

                if not valid:
                    connection.rollback()
                    return result

                _t0 = perf_counter()
                connection.executemany(
                    "DELETE FROM documents WHERE path = ?",
                    [(new_resolved,) for _, new_resolved, _ in valid],
                )
                _probe["delete_new_documents"] = perf_counter() - _t0

                _t0 = perf_counter()
                connection.executemany(
                    """
                    INSERT INTO documents (
                        path, name, category, extension, size, modified_ns,
                        content_hash, vector_indexed_hash, text_content,
                        extraction_error, metadata_json, extraction_method,
                        ocr_pages, total_pages, duplicate_of, is_deleted,
                        created_at, updated_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?,
                            CURRENT_TIMESTAMP)
                    """,
                    [
                        (
                            new_resolved,
                            document.name,
                            document.category,
                            document.extension,
                            document.size,
                            document.modified_ns,
                            old_rows[old_resolved]["content_hash"],
                            old_rows[old_resolved]["vector_indexed_hash"],
                            old_rows[old_resolved]["text_content"],
                            old_rows[old_resolved]["extraction_error"],
                            _relocated_metadata_json(
                                old_rows[old_resolved]["metadata_json"],
                                document.category,
                            ),
                            old_rows[old_resolved]["extraction_method"],
                            old_rows[old_resolved]["ocr_pages"],
                            old_rows[old_resolved]["total_pages"],
                            old_rows[old_resolved]["duplicate_of"],
                            old_rows[old_resolved]["created_at"],
                        )
                        for old_resolved, new_resolved, document in valid
                    ],
                )
                _probe["insert_documents"] = perf_counter() - _t0

                _t0 = perf_counter()
                connection.executemany(
                    """
                    UPDATE fragments
                    SET document_path = ?, category = ?
                    WHERE document_path = ?
                    """,
                    [
                        (
                            new_resolved,
                            document.category,
                            old_resolved,
                        )
                        for old_resolved, new_resolved, document in valid
                    ],
                )
                _probe["update_fragments"] = perf_counter() - _t0

                _t0 = perf_counter()
                connection.execute(
                    """
                    DELETE FROM fragments_fts
                    WHERE document_path IN (
                        SELECT old_path FROM lexia_relocation_map
                        UNION
                        SELECT new_path FROM lexia_relocation_map
                    )
                    """
                )
                _probe["fts_delete"] = perf_counter() - _t0

                _t0 = perf_counter()
                connection.execute(
                    """
                    INSERT INTO fragments_fts (
                        document_path, fragment_index, category,
                        document_name, text_content
                    )
                    SELECT
                        f.document_path,
                        f.fragment_index,
                        f.category,
                        m.new_name,
                        f.text_content
                    FROM fragments AS f
                    JOIN lexia_relocation_map AS m
                      ON m.new_path = f.document_path
                    """
                )
                _probe["fts_insert"] = perf_counter() - _t0

                _t0 = perf_counter()
                connection.execute(
                    """
                    UPDATE documents
                    SET duplicate_of = (
                        SELECT m.new_path
                        FROM lexia_relocation_map AS m
                        WHERE m.old_path = documents.duplicate_of
                    )
                    WHERE duplicate_of IN (
                        SELECT old_path FROM lexia_relocation_map
                    )
                    """
                )
                _probe["duplicate_update"] = perf_counter() - _t0

                _t0 = perf_counter()
                connection.execute(
                    """
                    DELETE FROM documents
                    WHERE path IN (
                        SELECT old_path FROM lexia_relocation_map
                    )
                    """
                )
                _probe["delete_old_documents"] = perf_counter() - _t0

                _t0 = perf_counter()
                old_location_rows = [
                    (old_rows[old_resolved]["content_hash"], old_resolved)
                    for old_resolved, _new_resolved, _document in valid
                ]
                new_location_rows = [
                    (old_rows[old_resolved]["content_hash"], new_resolved)
                    for old_resolved, new_resolved, _document in valid
                ]

                connection.executemany(
                    """
                    INSERT INTO document_locations (
                        content_hash, path, is_current
                    ) VALUES (?, ?, 0)
                    ON CONFLICT(content_hash, path) DO UPDATE SET
                        is_current = 0,
                        last_seen_at = CURRENT_TIMESTAMP
                    """,
                    old_location_rows,
                )

                connection.executemany(
                    """
                    INSERT INTO document_locations (
                        content_hash, path, is_current
                    ) VALUES (?, ?, 1)
                    ON CONFLICT(content_hash, path) DO UPDATE SET
                        is_current = 1,
                        last_seen_at = CURRENT_TIMESTAMP
                    """,
                    new_location_rows,
                )
                _probe["locations"] = perf_counter() - _t0

                _t0 = perf_counter()
                vector_rows = [
                    (
                        old_rows[old_resolved]["content_hash"],
                        old_resolved,
                        new_resolved,
                    )
                    for old_resolved, new_resolved, _document in valid
                    if (
                        old_rows[old_resolved]["duplicate_of"] is None
                        and old_rows[old_resolved]["vector_indexed_hash"]
                    )
                ]
                if vector_rows:
                    connection.executemany(
                        """
                        INSERT INTO vector_relocations (
                            content_hash, old_path, new_path
                        ) VALUES (?, ?, ?)
                        """,
                        vector_rows,
                    )
                _probe["vector_relocations"] = perf_counter() - _t0

                result["relocated"] = len(valid)
                _commit_started = perf_counter()

            if _commit_started is not None:
                _probe["commit_close"] = perf_counter() - _commit_started

        finally:
            _probe_total = perf_counter() - _probe_total_started
            self._relocation_probe_logger.info(
                "Catalog Relocation Batch 2.0 Timing | "
                "requested=%s | relocated=%s | "
                "prepare=%.3fs | load_old_rows=%.3fs | "
                "delete_new_documents=%.3fs | insert_documents=%.3fs | "
                "update_fragments=%.3fs | fts_delete=%.3fs | "
                "fts_insert=%.3fs | duplicate_update=%.3fs | "
                "delete_old_documents=%.3fs | locations=%.3fs | "
                "vector_relocations=%.3fs | commit_close=%.3fs | "
                "total=%.3fs",
                result["requested"],
                result["relocated"],
                _probe["prepare"],
                _probe["load_old_rows"],
                _probe["delete_new_documents"],
                _probe["insert_documents"],
                _probe["update_fragments"],
                _probe["fts_delete"],
                _probe["fts_insert"],
                _probe["duplicate_update"],
                _probe["delete_old_documents"],
                _probe["locations"],
                _probe["vector_relocations"],
                _probe["commit_close"],
                _probe_total,
            )

        return result
    # <<< LEXIA CATALOG RELOCATION BATCH 2.0


    # >>> LEXIA STARTUP RELOCATION ECHO SUPPRESSION 1.0
    def find_startup_relocation_echoes(
        self,
        changed_paths,
        deleted_paths,
    ) -> dict:
        changed = {
            str(Path(path).resolve())
            for path in changed_paths
        }
        deleted = {
            str(Path(path).resolve())
            for path in deleted_paths
        }

        result = {
            "changed": set(),
            "deleted": set(),
        }

        if not changed or not deleted:
            return result

        changed_list = list(changed)
        deleted_list = list(deleted)
        changed_ph = ",".join("?" for _ in changed_list)
        deleted_ph = ",".join("?" for _ in deleted_list)

        with self._connect() as connection:
            rows = connection.execute(
                f"""
                SELECT
                    cur.path AS current_path,
                    hist.path AS historical_path,
                    cur.content_hash AS content_hash
                FROM document_locations AS cur
                JOIN document_locations AS hist
                  ON hist.content_hash = cur.content_hash
                JOIN documents AS d
                  ON d.path = cur.path
                 AND d.content_hash = cur.content_hash
                 AND d.is_deleted = 0
                WHERE cur.is_current = 1
                  AND hist.is_current = 0
                  AND cur.path IN ({changed_ph})
                  AND hist.path IN ({deleted_ph})
                """,
                tuple(changed_list + deleted_list),
            ).fetchall()

        for row in rows:
            result["changed"].add(row["current_path"])
            result["deleted"].add(row["historical_path"])

        return result
    # <<< LEXIA STARTUP RELOCATION ECHO SUPPRESSION 1.0

    def pending_vector_relocations(self) -> list[dict]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT r.*, d.name, d.category, d.metadata_json
                FROM vector_relocations r
                LEFT JOIN documents d ON d.path = r.new_path
                WHERE r.status = 'pending'
                ORDER BY r.id
                """
            ).fetchall()

        result = []
        for row in rows:
            item = dict(row)
            item["metadata"] = json.loads(
                item.pop("metadata_json") or "{}"
            )
            result.append(item)
        return result

    def pending_vector_relocation_count(self) -> int:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT COUNT(*) AS total
                FROM vector_relocations
                WHERE status = 'pending'
                """
            ).fetchone()
        return int(row["total"] or 0)

    def complete_vector_relocation(self, relocation_id: int) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE vector_relocations
                SET status = 'completed',
                    completed_at = CURRENT_TIMESTAMP,
                    error = NULL
                WHERE id = ?
                """,
                (relocation_id,),
            )


    # >>> LEXIA VECTOR RELOCATION COMPLETION BATCH 1.0
    def complete_vector_relocations(self, relocation_ids) -> int:
        ids = [int(value) for value in relocation_ids]
        if not ids:
            return 0

        placeholders = ",".join("?" for _ in ids)

        with self._connect() as connection:
            cursor = connection.execute(
                f"""
                UPDATE vector_relocations
                SET status = 'completed',
                    completed_at = CURRENT_TIMESTAMP,
                    error = NULL
                WHERE id IN ({placeholders})
                """,
                tuple(ids),
            )

        return int(cursor.rowcount or 0)
    # <<< LEXIA VECTOR RELOCATION COMPLETION BATCH 1.0

    def fail_vector_relocation(
        self,
        relocation_id: int,
        error: str,
    ) -> None:
        with self._connect() as connection:
            connection.execute(
                "UPDATE vector_relocations SET error = ? WHERE id = ?",
                (error[:2000], relocation_id),
            )

    def save(self, document: Document) -> None:
        resolved_path = str(document.path.resolve())

        with self._connect() as connection:
            connection.execute(
                '''
                INSERT INTO documents (
                    path, name, category, extension, size, modified_ns,
                    content_hash, vector_indexed_hash, text_content,
                    extraction_error, metadata_json,
                    extraction_method, ocr_pages, total_pages,
                    duplicate_of, is_deleted, created_at, updated_at
                )
                VALUES (
                    ?, ?, ?, ?, ?, ?, ?, NULL, ?, ?, ?,
                    ?, ?, ?, ?, 0, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
                )
                ON CONFLICT(path) DO UPDATE SET
                    name = excluded.name,
                    category = excluded.category,
                    extension = excluded.extension,
                    size = excluded.size,
                    modified_ns = excluded.modified_ns,
                    content_hash = excluded.content_hash,
                    vector_indexed_hash = NULL,
                    text_content = excluded.text_content,
                    extraction_error = excluded.extraction_error,
                    metadata_json = excluded.metadata_json,
                    extraction_method = excluded.extraction_method,
                    ocr_pages = excluded.ocr_pages,
                    total_pages = excluded.total_pages,
                    duplicate_of = excluded.duplicate_of,
                    is_deleted = 0,
                    updated_at = CURRENT_TIMESTAMP
                ''',
                (
                    resolved_path,
                    document.name,
                    document.category,
                    document.extension,
                    document.size,
                    document.modified_ns,
                    document.content_hash,
                    document.text,
                    document.extraction_error,
                    json.dumps(
                        document.metadata,
                        ensure_ascii=False,
                    ),
                    document.extraction_method,
                    document.ocr_pages,
                    document.total_pages,
                    document.duplicate_of,
                ),
            )

            # >>> LEXIA AUTOSYNC LOCATIONS FIX 1.0
            connection.execute(
                """
                UPDATE document_locations
                SET is_current = 0
                WHERE path = ?
                  AND content_hash <> ?
                  AND is_current <> 0
                """,
                (resolved_path, document.content_hash),
            )
            # <<< LEXIA AUTOSYNC LOCATIONS FIX 1.0

            connection.execute(
                """
                INSERT INTO document_locations (
                    content_hash, path, is_current
                ) VALUES (?, ?, 1)
                ON CONFLICT(content_hash, path) DO UPDATE SET
                    is_current = 1,
                    last_seen_at = CURRENT_TIMESTAMP
                """,
                (document.content_hash, resolved_path),
            )

            connection.execute(
                "DELETE FROM fragments WHERE document_path = ?",
                (resolved_path,),
            )
            connection.execute(
                "DELETE FROM fragments_fts WHERE document_path = ?",
                (resolved_path,),
            )

            if document.is_duplicate:
                return

            connection.executemany(
                '''
                INSERT INTO fragments (
                    document_path, fragment_index, category,
                    text_content, start_char, end_char,
                    page_start, page_end
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''',
                [
                    (
                        resolved_path,
                        fragment.index,
                        fragment.category,
                        fragment.text,
                        fragment.start_char,
                        fragment.end_char,
                        fragment.page_start,
                        fragment.page_end,
                    )
                    for fragment in document.fragments
                ],
            )

            connection.executemany(
                '''
                INSERT INTO fragments_fts (
                    document_path, fragment_index, category,
                    document_name, text_content
                )
                VALUES (?, ?, ?, ?, ?)
                ''',
                [
                    (
                        resolved_path,
                        fragment.index,
                        fragment.category,
                        document.name,
                        fragment.text,
                    )
                    for fragment in document.fragments
                ],
            )

    def purge_document(self, path: str | Path) -> dict:
        """Elimina definitivamente un documento y sus derivados del catalogo."""
        resolved_path = str(Path(path).resolve())
        with self._connect() as connection:
            row = connection.execute(
                "SELECT content_hash FROM documents WHERE path = ?",
                (resolved_path,),
            ).fetchone()
            if row is None:
                return {"deleted": False, "fragments_deleted": 0,
                        "duplicates_released": 0}

            fragments = int(connection.execute(
                "SELECT COUNT(*) FROM fragments WHERE document_path = ?",
                (resolved_path,),
            ).fetchone()[0])
            duplicates = connection.execute(
                """
                UPDATE documents
                SET duplicate_of = NULL,
                    vector_indexed_hash = NULL,
                    updated_at = CURRENT_TIMESTAMP
                WHERE duplicate_of = ?
                """,
                (resolved_path,),
            ).rowcount
            connection.execute(
                "DELETE FROM fragments_fts WHERE document_path = ?",
                (resolved_path,),
            )
            connection.execute(
                "DELETE FROM fragments WHERE document_path = ?",
                (resolved_path,),
            )
            connection.execute(
                "DELETE FROM document_locations WHERE path = ?",
                (resolved_path,),
            )
            connection.execute(
                "DELETE FROM vector_relocations WHERE old_path = ? OR new_path = ?",
                (resolved_path, resolved_path),
            )
            connection.execute(
                "DELETE FROM documents WHERE path = ?",
                (resolved_path,),
            )

        return {
            "deleted": True,
            "fragments_deleted": fragments,
            "duplicates_released": int(duplicates or 0),
        }


    def mark_paths_deleted(
        self,
        paths: set[str] | list[str],
    ) -> list[str]:
        resolved_paths = {
            str(Path(path).resolve())
            for path in paths
        }

        if not resolved_paths:
            return []

        deleted = []

        with self._connect() as connection:
            for path in resolved_paths:
                row = connection.execute(
                    """
                    SELECT path
                    FROM documents
                    WHERE path = ?
                      AND is_deleted = 0
                    """,
                    (path,),
                ).fetchone()

                if not row:
                    continue

                connection.execute(
                    """
                    UPDATE documents
                    SET is_deleted = 1,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE path = ?
                    """,
                    (path,),
                )
                connection.execute(
                    """
                    UPDATE document_locations
                    SET is_current = 0,
                        last_seen_at = CURRENT_TIMESTAMP
                    WHERE path = ?
                    """,
                    (path,),
                )
                connection.execute(
                    """
                    DELETE FROM fragments_fts
                    WHERE document_path = ?
                    """,
                    (path,),
                )
                deleted.append(path)

        return deleted

    def mark_missing_as_deleted(self, active_paths: set[str]) -> list[str]:
        with self._connect() as connection:
            current_rows = connection.execute(
                "SELECT path FROM documents WHERE is_deleted = 0"
            ).fetchall()

            missing = [
                row["path"]
                for row in current_rows
                if row["path"] not in active_paths
            ]

            connection.executemany(
                '''
                UPDATE documents
                SET is_deleted = 1,
                    vector_indexed_hash = NULL,
                    updated_at = CURRENT_TIMESTAMP
                WHERE path = ?
                ''',
                [(path,) for path in missing],
            )

            connection.executemany(
                "DELETE FROM fragments_fts WHERE document_path = ?",
                [(path,) for path in missing],
            )

            connection.executemany(
                """
                UPDATE document_locations
                SET is_current = 0,
                    last_seen_at = CURRENT_TIMESTAMP
                WHERE path = ?
                """,
                [(path,) for path in missing],
            )

        return missing

    def retryable_error_paths(self) -> list[str]:
        """
        Devuelve documentos activos con error de extracción que aún existen
        en disco. Se usan para recuperación explícita.
        """
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT path
                FROM documents
                WHERE is_deleted = 0
                  AND extraction_error IS NOT NULL
                  AND TRIM(extraction_error) != ''
                ORDER BY path
                """
            ).fetchall()

        return [
            str(Path(row["path"]).resolve())
            for row in rows
            if Path(row["path"]).exists()
        ]


    def pending_vector_document_count(self) -> int:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT COUNT(*) AS total
                FROM documents
                WHERE is_deleted = 0
                  AND extraction_error IS NULL
                  AND duplicate_of IS NULL
                  AND content_hash != COALESCE(vector_indexed_hash, '')
                """
            ).fetchone()
        return int(row["total"] or 0)

    def pending_vector_documents(
        self,
        paths: list[str | Path] | None = None,
    ) -> list[Document]:
        target_paths = [str(Path(path).resolve()) for path in (paths or [])]
        path_clause = ""
        params: list[object] = []
        if target_paths:
            placeholders = ",".join("?" for _ in target_paths)
            path_clause = f" AND path IN ({placeholders})"
            params.extend(target_paths)
        with self._connect() as connection:
            document_rows = connection.execute(
                f'''
                SELECT *
                FROM documents
                WHERE is_deleted = 0
                  AND extraction_error IS NULL
                  AND duplicate_of IS NULL
                  AND content_hash != COALESCE(vector_indexed_hash, '')
                  {path_clause}
                ORDER BY path
                ''',
                params,
            ).fetchall()

            documents: list[Document] = []

            for row in document_rows:
                fragment_rows = connection.execute(
                    '''
                    SELECT *
                    FROM fragments
                    WHERE document_path = ?
                    ORDER BY fragment_index
                    ''',
                    (row["path"],),
                ).fetchall()

                document = Document(
                    name=row["name"],
                    path=Path(row["path"]),
                    category=row["category"],
                    extension=row["extension"],
                    size=row["size"],
                    modified_ns=row["modified_ns"],
                    content_hash=row["content_hash"],
                    text=row["text_content"],
                    extraction_error=row["extraction_error"],
                    metadata=json.loads(row["metadata_json"] or "{}"),
                    extraction_method=row["extraction_method"],
                    ocr_pages=row["ocr_pages"],
                    total_pages=row["total_pages"],
                    duplicate_of=row["duplicate_of"],
                )

                document.fragments = [
                    Fragment(
                        document_name=document.name,
                        document_path=document.path,
                        category=fragment_row["category"],
                        index=fragment_row["fragment_index"],
                        text=fragment_row["text_content"],
                        start_char=fragment_row["start_char"],
                        end_char=fragment_row["end_char"],
                        page_start=fragment_row["page_start"],
                        page_end=fragment_row["page_end"],
                    )
                    for fragment_row in fragment_rows
                ]

                documents.append(document)

        return documents

    def mark_vector_indexed(
        self,
        document_path: str | Path,
        content_hash: str,
    ) -> None:
        # >>> LEXIA VECTOR HASH COMMIT FIX 1.0
        resolved_path = str(Path(document_path).resolve())

        with self._connect() as connection:
            cursor = connection.execute(
                """
                UPDATE documents
                SET vector_indexed_hash = ?
                WHERE path = ?
                  AND content_hash = ?
                """,
                (
                    content_hash,
                    resolved_path,
                    content_hash,
                ),
            )

            if cursor.rowcount != 1:
                raise RuntimeError(
                    "No se pudo confirmar la indexacion vectorial "
                    f"para {resolved_path}: "
                    f"filas actualizadas={cursor.rowcount}"
                )

            connection.commit()

            row = connection.execute(
                """
                SELECT content_hash, vector_indexed_hash
                FROM documents
                WHERE path = ?
                """,
                (resolved_path,),
            ).fetchone()

            if (
                row is None
                or row["content_hash"] != content_hash
                or row["vector_indexed_hash"] != content_hash
            ):
                raise RuntimeError(
                    "La confirmacion vectorial no quedo persistida "
                    f"para {resolved_path}"
                )
        # <<< LEXIA VECTOR HASH COMMIT FIX 1.0

    def direct_document_search(
        self,
        query: str,
        limit: int = 25,
        category: str | None = None,
    ) -> list[dict]:
        clean = str(query or '').strip()
        if not clean:
            return []

        pattern = f'%{clean}%'
        prefix = f'{clean}%'

        sql = """
            SELECT
                d.path,
                d.name,
                d.category,
                d.metadata_json,
                COALESCE(
                    (
                        SELECT f.text_content
                        FROM fragments f
                        WHERE f.document_path = d.path
                        ORDER BY f.fragment_index
                        LIMIT 1
                    ),
                    d.text_content,
                    ''
                ) AS text_content,
                0 AS fragment_index,
                (
                    SELECT f.page_start
                    FROM fragments f
                    WHERE f.document_path = d.path
                    ORDER BY f.fragment_index
                    LIMIT 1
                ) AS page_start,
                (
                    SELECT f.page_end
                    FROM fragments f
                    WHERE f.document_path = d.path
                    ORDER BY f.fragment_index
                    LIMIT 1
                ) AS page_end
            FROM documents d
            WHERE d.is_deleted = 0
              AND (
                    d.name LIKE ? COLLATE NOCASE
                    OR d.path LIKE ? COLLATE NOCASE
              )
        """
        params = [pattern, pattern]

        if category:
            sql += ' AND d.category = ?'
            params.append(category)

        sql += """
            ORDER BY
                CASE
                    WHEN d.name = ? COLLATE NOCASE THEN 0
                    WHEN d.name LIKE ? COLLATE NOCASE THEN 1
                    WHEN d.path LIKE ? COLLATE NOCASE THEN 2
                    ELSE 3
                END,
                d.name COLLATE NOCASE
            LIMIT ?
        """
        params.extend([
            clean,
            prefix,
            prefix,
            max(1, int(limit)),
        ])

        with self._connect() as connection:
            rows = connection.execute(sql, params).fetchall()

        return [dict(row) for row in rows]

    def lexical_search(
        self,
        query: str,
        limit: int,
        category: str | None = None,
    ) -> list[dict]:
        sql = '''
            SELECT
                fts.document_path,
                CAST(fts.fragment_index AS INTEGER) AS fragment_index,
                fts.category,
                fts.document_name,
                fts.text_content,
                f.page_start,
                f.page_end,
                bm25(fragments_fts) AS lexical_score
            FROM fragments_fts AS fts
            JOIN fragments AS f
              ON f.document_path = fts.document_path
             AND f.fragment_index = CAST(fts.fragment_index AS INTEGER)
            WHERE fragments_fts MATCH ?
        '''
        params: list[object] = [query]

        if category:
            sql += " AND fts.category = ?"
            params.append(category)

        sql += " ORDER BY lexical_score LIMIT ?"
        params.append(limit)

        try:
            with self._connect() as connection:
                rows = connection.execute(sql, params).fetchall()
        except sqlite3.OperationalError:
            return []

        return [dict(row) for row in rows]


    def find_path_by_hash(
        self,
        content_hash: str,
        exclude_path: str | None = None,
    ) -> str | None:
        sql = '''
            SELECT path
            FROM documents
            WHERE content_hash = ?
              AND is_deleted = 0
              AND duplicate_of IS NULL
        '''
        params: list[object] = [content_hash]

        if exclude_path:
            sql += " AND path != ?"
            params.append(exclude_path)

        sql += " ORDER BY updated_at ASC LIMIT 1"

        with self._connect() as connection:
            row = connection.execute(sql, params).fetchone()

        return row["path"] if row else None

    def processing_stats(self) -> dict[str, int]:
        with self._connect() as connection:
            row = connection.execute(
                '''
                SELECT
                    COUNT(*) AS total,
                    SUM(CASE WHEN duplicate_of IS NOT NULL THEN 1 ELSE 0 END)
                        AS duplicates,
                    SUM(CASE WHEN ocr_pages > 0 THEN 1 ELSE 0 END)
                        AS with_ocr,
                    SUM(CASE WHEN extraction_error IS NOT NULL THEN 1 ELSE 0 END)
                        AS with_error
                FROM documents
                WHERE is_deleted = 0
                '''
            ).fetchone()

        return {
            "total": int(row["total"] or 0),
            "duplicates": int(row["duplicates"] or 0),
            "with_ocr": int(row["with_ocr"] or 0),
            "with_error": int(row["with_error"] or 0),
        }

    def stats(self) -> dict[str, int]:
        with self._connect() as connection:
            documents = connection.execute(
                "SELECT COUNT(*) AS total FROM documents WHERE is_deleted = 0"
            ).fetchone()["total"]
            fragments = connection.execute(
                '''
                SELECT COUNT(*) AS total
                FROM fragments f
                JOIN documents d ON d.path = f.document_path
                WHERE d.is_deleted = 0
                '''
            ).fetchone()["total"]

        return {
            "documents": int(documents),
            "fragments": int(fragments),
        }


    def category_counts(self) -> dict[str, int]:
        """Devuelve las categorías documentales activas y sus cantidades."""
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT category, COUNT(*) AS total
                FROM documents
                WHERE is_deleted = 0
                GROUP BY category
                ORDER BY category COLLATE NOCASE
                """
            ).fetchall()

        return {
            str(row["category"] or "Sin categoría"): int(row["total"] or 0)
            for row in rows
        }

    def folder_counts(self) -> dict[str, int]:
        """Devuelve carpetas físicas de documentos activos y sus cantidades."""
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT path
                FROM documents
                WHERE is_deleted = 0
                ORDER BY path COLLATE NOCASE
                """
            ).fetchall()

        folders = [Path(row["path"]).parent for row in rows]
        if not folders:
            return {}

        common_root = Path(os.path.commonpath([str(path) for path in folders]))
        counts: dict[str, int] = {}
        for folder in folders:
            current = folder
            while current != common_root:
                key = str(current)
                counts[key] = counts.get(key, 0) + 1
                if current.parent == current:
                    break
                current = current.parent
        return counts

    def browse_documents(
        self,
        query: str = "",
        category: str | None = None,
        folder: str | Path | None = None,
        include_subfolders: bool = True,
        limit: int = 200,
    ) -> list[dict]:
        """Lista documentos con filtros combinables, sin modificar el catálogo."""
        sql = """
            SELECT
                path, name, category, extension, size,
                metadata_json, updated_at
            FROM documents
            WHERE is_deleted = 0
        """
        params: list[object] = []
        clean = str(query or "").strip()

        if clean:
            pattern = f"%{clean}%"
            sql += " AND (name LIKE ? COLLATE NOCASE OR path LIKE ? COLLATE NOCASE)"
            params.extend([pattern, pattern])

        if category:
            sql += " AND category = ?"
            params.append(str(category))

        if folder:
            normalized = str(Path(folder).resolve())
            if include_subfolders:
                sql += " AND (path LIKE ? COLLATE NOCASE OR path LIKE ? COLLATE NOCASE)"
                params.extend([
                    normalized + "\\%",
                    normalized + "/%",
                ])
            else:
                # La comparación exacta de la carpeta se completa en Python.
                sql += " AND (path LIKE ? COLLATE NOCASE OR path LIKE ? COLLATE NOCASE)"
                params.extend([
                    normalized + "\\%",
                    normalized + "/%",
                ])

        sql += " ORDER BY name COLLATE NOCASE, path COLLATE NOCASE LIMIT ?"
        scan_limit = max(1, int(limit))
        params.append(scan_limit if include_subfolders or not folder else scan_limit * 20)

        with self._connect() as connection:
            rows = connection.execute(sql, params).fetchall()

        result = []
        exact_folder = str(Path(folder).resolve()) if folder else None
        for row in rows:
            if exact_folder and not include_subfolders:
                if str(Path(row["path"]).parent) != exact_folder:
                    continue
            item = dict(row)
            item["metadata"] = json.loads(item.pop("metadata_json") or "{}")
            result.append(item)
            if len(result) >= scan_limit:
                break

        return result


    def browse_documents_multi(
        self, query: str = "", folders: list[str] | None = None,
        include_subfolders: bool = True, limit: int | None = None,
        categories: list[str] | None = None,
    ) -> list[dict]:
        """Consulta documentos; el texto libre se aplica sólo al nombre."""
        sql = """SELECT path,name,category,extension,size,metadata_json,updated_at
                 FROM documents WHERE is_deleted=0"""
        params: list[object] = []
        clean = str(query or "").strip()
        if clean:
            pattern = f"%{clean}%"
            sql += " AND name LIKE ? COLLATE NOCASE"
            params.append(pattern)
        normalized_categories = [
            str(category) for category in (categories or []) if category
        ]
        if normalized_categories:
            placeholders = ",".join("?" for _ in normalized_categories)
            sql += f" AND category IN ({placeholders})"
            params.extend(normalized_categories)
        normalized = [str(Path(folder)) for folder in (folders or [])]
        if normalized:
            clauses = []
            for folder in normalized:
                clauses.append("(path LIKE ? COLLATE NOCASE OR path LIKE ? COLLATE NOCASE)")
                params.extend([folder + "\\%", folder + "/%"])
            sql += " AND (" + " OR ".join(clauses) + ")"
        sql += " ORDER BY name COLLATE NOCASE,path COLLATE NOCASE"
        if limit is not None:
            sql += " LIMIT ?"
            params.append(max(1, int(limit)) * (20 if normalized and not include_subfolders else 1))
        with self._connect() as connection:
            rows = connection.execute(sql, params).fetchall()
        result = []
        normalized_set = set(normalized)
        for row in rows:
            if normalized and not include_subfolders:
                if str(Path(row["path"]).parent) not in normalized_set:
                    continue
            item = dict(row)
            item["metadata"] = json.loads(item.pop("metadata_json") or "{}")
            result.append(item)
            if limit is not None and len(result) >= max(1, int(limit)):
                break
        return result

    def recent_documents(
        self,
        limit: int = 200,
        categories: list[str] | None = None,
    ) -> list[dict]:
        """Devuelve los documentos activos actualizados más recientemente."""
        sql = """
            SELECT
                path, name, category, extension, size,
                metadata_json, updated_at
            FROM documents
            WHERE is_deleted = 0
        """
        params: list[object] = []
        normalized_categories = [
            str(category)
            for category in (categories or [])
            if category
        ]
        if normalized_categories:
            placeholders = ",".join("?" for _ in normalized_categories)
            sql += f" AND category IN ({placeholders})"
            params.extend(normalized_categories)

        sql += " ORDER BY updated_at DESC, name COLLATE NOCASE LIMIT ?"
        params.append(max(1, int(limit)))

        with self._connect() as connection:
            rows = connection.execute(sql, params).fetchall()

        result = []
        for row in rows:
            item = dict(row)
            item["metadata"] = json.loads(
                item.pop("metadata_json") or "{}"
            )
            result.append(item)
        return result

    def list_documents(
        self,
        category: str | None = None,
        limit: int = 500,
    ) -> list[dict]:
        sql = '''
            SELECT
                path, name, category, extension, size,
                metadata_json, updated_at
            FROM documents
            WHERE is_deleted = 0
        '''
        params: list[object] = []

        if category:
            sql += " AND category = ?"
            params.append(category)

        sql += " ORDER BY name LIMIT ?"
        params.append(limit)

        with self._connect() as connection:
            rows = connection.execute(sql, params).fetchall()

        result = []
        for row in rows:
            item = dict(row)
            item["metadata"] = json.loads(item.pop("metadata_json") or "{}")
            result.append(item)

        return result
