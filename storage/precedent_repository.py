import sqlite3
from pathlib import Path


class PrecedentRepository:
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
                CREATE TABLE IF NOT EXISTS precedents (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    proposition TEXT NOT NULL,
                    source_document TEXT NOT NULL,
                    source_path TEXT NOT NULL,
                    page_label TEXT NOT NULL DEFAULT '',
                    court TEXT NOT NULL DEFAULT '',
                    date TEXT NOT NULL DEFAULT '',
                    matter TEXT NOT NULL DEFAULT '',
                    favorable INTEGER NOT NULL DEFAULT 1,
                    confidence REAL NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                '''
            )

    def add(
        self,
        title: str,
        proposition: str,
        source_document: str,
        source_path: str,
        page_label: str = "",
        court: str = "",
        date: str = "",
        matter: str = "",
        favorable: bool = True,
        confidence: float = 0.0,
    ) -> int:
        with self._connect() as connection:
            cursor = connection.execute(
                '''
                INSERT INTO precedents (
                    title, proposition, source_document, source_path,
                    page_label, court, date, matter, favorable, confidence
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''',
                (
                    title.strip(),
                    proposition.strip(),
                    source_document,
                    source_path,
                    page_label,
                    court,
                    date,
                    matter,
                    1 if favorable else 0,
                    confidence,
                ),
            )
            return int(cursor.lastrowid)

    def list(self, limit: int = 200) -> list[dict]:
        with self._connect() as connection:
            rows = connection.execute(
                '''
                SELECT *
                FROM precedents
                ORDER BY id DESC
                LIMIT ?
                ''',
                (limit,),
            ).fetchall()
        return [dict(row) for row in rows]

    def delete(self, precedent_id: int) -> None:
        with self._connect() as connection:
            connection.execute(
                "DELETE FROM precedents WHERE id = ?",
                (precedent_id,),
            )
