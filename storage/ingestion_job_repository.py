import json
import sqlite3
from datetime import datetime
from pathlib import Path


class IngestionJobRepository:
    def __init__(self, database_path: str | Path):
        self.database_path = Path(database_path)
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                '''
                CREATE TABLE IF NOT EXISTS ingestion_jobs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    status TEXT NOT NULL,
                    total_documents INTEGER NOT NULL,
                    processed_documents INTEGER NOT NULL DEFAULT 0,
                    current_path TEXT,
                    stats_json TEXT NOT NULL DEFAULT '{}',
                    started_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    finished_at TEXT
                );
                '''
            )

    def create(self, total_documents: int) -> int:
        with self._connect() as connection:
            cursor = connection.execute(
                '''
                INSERT INTO ingestion_jobs (
                    status,
                    total_documents,
                    processed_documents,
                    stats_json
                )
                VALUES ('running', ?, 0, '{}')
                ''',
                (total_documents,),
            )
            return int(cursor.lastrowid)

    def checkpoint(
        self,
        job_id: int,
        processed_documents: int,
        current_path: str,
        stats: dict,
    ) -> None:
        with self._connect() as connection:
            connection.execute(
                '''
                UPDATE ingestion_jobs
                SET processed_documents = ?,
                    current_path = ?,
                    stats_json = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                ''',
                (
                    processed_documents,
                    current_path,
                    json.dumps(
                        stats,
                        ensure_ascii=False,
                    ),
                    job_id,
                ),
            )

    def finish(
        self,
        job_id: int,
        status: str,
        stats: dict,
    ) -> None:
        with self._connect() as connection:
            connection.execute(
                '''
                UPDATE ingestion_jobs
                SET status = ?,
                    stats_json = ?,
                    updated_at = CURRENT_TIMESTAMP,
                    finished_at = CURRENT_TIMESTAMP
                WHERE id = ?
                ''',
                (
                    status,
                    json.dumps(
                        stats,
                        ensure_ascii=False,
                    ),
                    job_id,
                ),
            )

    def latest(self) -> dict | None:
        with self._connect() as connection:
            row = connection.execute(
                '''
                SELECT *
                FROM ingestion_jobs
                ORDER BY id DESC
                LIMIT 1
                '''
            ).fetchone()

        if not row:
            return None

        result = dict(row)
        result["stats"] = json.loads(
            result.pop("stats_json") or "{}"
        )
        return result
