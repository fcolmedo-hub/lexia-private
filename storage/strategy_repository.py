import sqlite3
from pathlib import Path


class StrategyRepository:
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
                CREATE TABLE IF NOT EXISTS strategies (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    case_name TEXT NOT NULL,
                    thesis TEXT NOT NULL,
                    report TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                '''
            )

    def save(self, case_name: str, thesis: str, report: str) -> int:
        with self._connect() as connection:
            cursor = connection.execute(
                '''
                INSERT INTO strategies (
                    case_name, thesis, report
                )
                VALUES (?, ?, ?)
                ''',
                (case_name.strip(), thesis.strip(), report),
            )
            return int(cursor.lastrowid)

    def list(self, limit: int = 100) -> list[dict]:
        with self._connect() as connection:
            rows = connection.execute(
                '''
                SELECT *
                FROM strategies
                ORDER BY id DESC
                LIMIT ?
                ''',
                (limit,),
            ).fetchall()
        return [dict(row) for row in rows]
