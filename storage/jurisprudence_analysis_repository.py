import json
import sqlite3
from pathlib import Path


class JurisprudenceAnalysisRepository:
    def __init__(self, database_path: str | Path):
        self.database_path = Path(database_path)
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self):
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS jurisprudence_analyses (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    content_hash TEXT NOT NULL,
                    source_name TEXT NOT NULL,
                    source_path TEXT NOT NULL DEFAULT '',
                    analysis_type TEXT NOT NULL,
                    analysis_text TEXT NOT NULL,
                    metadata_json TEXT NOT NULL DEFAULT '{}',
                    pages INTEGER,
                    chunks INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(content_hash, analysis_type)
                );
                """
            )

    def find(self, content_hash: str, analysis_type: str) -> dict | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT * FROM jurisprudence_analyses
                WHERE content_hash = ? AND analysis_type = ?
                ORDER BY id DESC LIMIT 1
                """,
                (content_hash, analysis_type),
            ).fetchone()
        return self._decode(row) if row else None

    def save(
        self,
        content_hash: str,
        source_name: str,
        source_path: str,
        analysis_type: str,
        analysis_text: str,
        metadata: dict,
        pages: int | None,
        chunks: int,
    ) -> int:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO jurisprudence_analyses (
                    content_hash, source_name, source_path,
                    analysis_type, analysis_text, metadata_json,
                    pages, chunks
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(content_hash, analysis_type) DO UPDATE SET
                    source_name = excluded.source_name,
                    source_path = excluded.source_path,
                    analysis_text = excluded.analysis_text,
                    metadata_json = excluded.metadata_json,
                    pages = excluded.pages,
                    chunks = excluded.chunks,
                    created_at = CURRENT_TIMESTAMP
                """,
                (
                    content_hash,
                    source_name,
                    source_path,
                    analysis_type,
                    analysis_text,
                    json.dumps(metadata, ensure_ascii=False),
                    pages,
                    chunks,
                ),
            )
            row = connection.execute(
                """
                SELECT id FROM jurisprudence_analyses
                WHERE content_hash = ? AND analysis_type = ?
                """,
                (content_hash, analysis_type),
            ).fetchone()
        return int(row["id"])

    def list_recent(self, limit: int = 30) -> list[dict]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM jurisprudence_analyses
                ORDER BY created_at DESC, id DESC LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [self._decode(row) for row in rows]

    def _decode(self, row) -> dict:
        item = dict(row)
        item["metadata"] = json.loads(
            item.pop("metadata_json") or "{}"
        )
        return item
