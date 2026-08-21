import json
import sqlite3
from pathlib import Path

from models.query_interpretation import QueryInterpretation


class QueryInterpretationRepository:
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
                CREATE TABLE IF NOT EXISTS query_interpretations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    original_query TEXT NOT NULL,
                    interpretation_json TEXT NOT NULL,
                    corrected INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                '''
            )

    def save(
        self,
        interpretation: QueryInterpretation,
        corrected: bool = False,
    ) -> int:
        with self._connect() as connection:
            cursor = connection.execute(
                '''
                INSERT INTO query_interpretations (
                    original_query,
                    interpretation_json,
                    corrected
                )
                VALUES (?, ?, ?)
                ''',
                (
                    interpretation.original_query,
                    json.dumps(
                        interpretation.to_dict(),
                        ensure_ascii=False,
                    ),
                    1 if corrected else 0,
                ),
            )
            return int(cursor.lastrowid)

    def list_recent(self, limit: int = 30) -> list[dict]:
        with self._connect() as connection:
            rows = connection.execute(
                '''
                SELECT *
                FROM query_interpretations
                ORDER BY id DESC
                LIMIT ?
                ''',
                (limit,),
            ).fetchall()

        result = []

        for row in rows:
            item = dict(row)
            item["interpretation"] = json.loads(
                item.pop("interpretation_json")
            )
            result.append(item)

        return result
