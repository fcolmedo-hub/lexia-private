import sqlite3
from pathlib import Path


class DraftingRepository:
    def __init__(self, database_path: str | Path):
        self.database_path = Path(database_path)
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self):
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize(self):
        with self._connect() as connection:
            connection.executescript(
                '''
                CREATE TABLE IF NOT EXISTS drafts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    document_type TEXT NOT NULL,
                    content TEXT NOT NULL,
                    version INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                '''
            )

    def save(
        self,
        title: str,
        document_type: str,
        content: str,
    ) -> int:
        with self._connect() as connection:
            row = connection.execute(
                '''
                SELECT COALESCE(MAX(version), 0) AS max_version
                FROM drafts
                WHERE title = ?
                ''',
                (title.strip(),),
            ).fetchone()

            version = int(row["max_version"]) + 1

            cursor = connection.execute(
                '''
                INSERT INTO drafts (
                    title, document_type, content, version
                )
                VALUES (?, ?, ?, ?)
                ''',
                (
                    title.strip(),
                    document_type.strip(),
                    content,
                    version,
                ),
            )
            return int(cursor.lastrowid)

    def list(self, limit: int = 100) -> list[dict]:
        with self._connect() as connection:
            rows = connection.execute(
                '''
                SELECT *
                FROM drafts
                ORDER BY id DESC
                LIMIT ?
                ''',
                (limit,),
            ).fetchall()
        return [dict(row) for row in rows]
