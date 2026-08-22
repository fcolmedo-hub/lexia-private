import sqlite3
from pathlib import Path


class OCRQueueRepository:
    def __init__(self, database_path: str | Path):
        self.database_path = Path(database_path)
        self.database_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(
            self.database_path,
            timeout=30,
        )
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                PRAGMA journal_mode = WAL;

                CREATE TABLE IF NOT EXISTS ocr_queue (
                    document_path TEXT PRIMARY KEY,
                    document_name TEXT NOT NULL,
                    total_pages INTEGER,
                    status TEXT NOT NULL DEFAULT 'pending',
                    selected INTEGER NOT NULL DEFAULT 1,
                    progress_page INTEGER NOT NULL DEFAULT 0,
                    error TEXT NOT NULL DEFAULT '',
                    added_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    completed_at TEXT
                );

                CREATE INDEX IF NOT EXISTS idx_ocr_queue_status
                ON ocr_queue(status);
                """
            )

    def enqueue(
        self,
        document_path: str,
        document_name: str,
        total_pages: int | None,
    ) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO ocr_queue (
                    document_path,
                    document_name,
                    total_pages,
                    status,
                    selected,
                    progress_page,
                    error,
                    updated_at
                )
                VALUES (?, ?, ?, 'pending', 1, 0, '',
                        CURRENT_TIMESTAMP)
                ON CONFLICT(document_path) DO UPDATE SET
                    document_name = excluded.document_name,
                    total_pages = excluded.total_pages,
                    status = CASE
                        WHEN ocr_queue.status = 'completed'
                        THEN ocr_queue.status
                        ELSE 'pending'
                    END,
                    error = '',
                    updated_at = CURRENT_TIMESTAMP
                """,
                (
                    document_path,
                    document_name,
                    total_pages,
                ),
            )

    def list_pending(self) -> list[dict]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT *
                FROM ocr_queue
                WHERE status IN ('pending', 'error', 'processing')
                ORDER BY added_at, document_name
                """
            ).fetchall()
        return [dict(row) for row in rows]

    def get(self, document_path: str) -> dict | None:
        """Return one queue item without loading the complete OCR queue."""
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT *
                FROM ocr_queue
                WHERE document_path = ?
                LIMIT 1
                """,
                (document_path,),
            ).fetchone()
        return dict(row) if row is not None else None

    def get_selected_paths(self) -> list[str]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT document_path
                FROM ocr_queue
                WHERE selected = 1
                  AND status IN ('pending', 'error')
                ORDER BY added_at
                """
            ).fetchall()
        return [row["document_path"] for row in rows]

    def set_selected(
        self,
        document_path: str,
        selected: bool,
    ) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE ocr_queue
                SET selected = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE document_path = ?
                """,
                (1 if selected else 0, document_path),
            )

    def select_all(self, selected: bool) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE ocr_queue
                SET selected = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE status IN ('pending', 'error')
                """,
                (1 if selected else 0,),
            )

    def mark_processing(self, path: str) -> None:
        self._update(
            path,
            status="processing",
            progress_page=0,
            error="",
        )

    def mark_pending(self, path: str) -> None:
        self._update(
            path,
            status="pending",
            error="",
        )

    def recover_interrupted(self) -> int:
        with self._connect() as connection:
            cursor = connection.execute(
                """
                UPDATE ocr_queue
                SET status = 'pending', error = '',
                    updated_at = CURRENT_TIMESTAMP
                WHERE status = 'processing'
                """
            )
            return int(cursor.rowcount or 0)

    def update_progress(
        self,
        path: str,
        page: int,
    ) -> None:
        self._update(
            path,
            status="processing",
            progress_page=page,
        )

    def mark_completed(self, path: str) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE ocr_queue
                SET status = 'completed',
                    selected = 0,
                    error = '',
                    completed_at = CURRENT_TIMESTAMP,
                    updated_at = CURRENT_TIMESTAMP
                WHERE document_path = ?
                """,
                (path,),
            )

    def mark_error(
        self,
        path: str,
        error: str,
    ) -> None:
        self._update(
            path,
            status="error",
            error=error,
        )

    def remove_completed(self) -> int:
        with self._connect() as connection:
            cursor = connection.execute(
                """
                DELETE FROM ocr_queue
                WHERE status = 'completed'
                """
            )
            return cursor.rowcount

    def stats(self) -> dict:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT status, COUNT(*) AS total
                FROM ocr_queue
                GROUP BY status
                """
            ).fetchall()

        result = {
            "pending": 0,
            "processing": 0,
            "completed": 0,
            "error": 0,
        }
        for row in rows:
            result[row["status"]] = row["total"]
        return result

    def _update(self, path: str, **changes) -> None:
        allowed = {
            "status",
            "progress_page",
            "error",
        }
        values = {
            key: value
            for key, value in changes.items()
            if key in allowed
        }
        if not values:
            return

        assignments = ", ".join(
            f"{key} = ?" for key in values
        )
        parameters = list(values.values()) + [path]

        with self._connect() as connection:
            connection.execute(
                f"""
                UPDATE ocr_queue
                SET {assignments},
                    updated_at = CURRENT_TIMESTAMP
                WHERE document_path = ?
                """,
                parameters,
            )
