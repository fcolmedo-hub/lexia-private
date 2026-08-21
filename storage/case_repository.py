import sqlite3
from pathlib import Path

from models.search_result import SearchResult


class CaseRepository:
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
                CREATE TABLE IF NOT EXISTS cases (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    description TEXT NOT NULL DEFAULT '',
                    notes TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS case_sources (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    case_id INTEGER NOT NULL,
                    document_name TEXT NOT NULL,
                    document_path TEXT NOT NULL,
                    category TEXT NOT NULL,
                    fragment_index INTEGER NOT NULL,
                    text_content TEXT NOT NULL,
                    score REAL NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS case_outputs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    case_id INTEGER NOT NULL,
                    output_type TEXT NOT NULL,
                    title TEXT NOT NULL,
                    content TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                '''
            )

    def create_case(self, name: str, description: str = "") -> int:
        with self._connect() as connection:
            cursor = connection.execute(
                "INSERT INTO cases (name, description) VALUES (?, ?)",
                (name.strip(), description.strip()),
            )
            return int(cursor.lastrowid)

    def list_cases(self) -> list[dict]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM cases ORDER BY updated_at DESC, id DESC"
            ).fetchall()
        return [dict(row) for row in rows]

    def update_notes(self, case_id: int, notes: str) -> None:
        with self._connect() as connection:
            connection.execute(
                '''
                UPDATE cases
                SET notes = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                ''',
                (notes, case_id),
            )

    def add_source(self, case_id: int, result: SearchResult) -> None:
        with self._connect() as connection:
            connection.execute(
                '''
                INSERT INTO case_sources (
                    case_id, document_name, document_path, category,
                    fragment_index, text_content, score
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ''',
                (
                    case_id,
                    result.document_name,
                    str(result.document_path),
                    result.category,
                    result.fragment_index,
                    result.text,
                    result.score,
                ),
            )

    def list_sources(self, case_id: int) -> list[dict]:
        with self._connect() as connection:
            rows = connection.execute(
                '''
                SELECT * FROM case_sources
                WHERE case_id = ?
                ORDER BY id DESC
                ''',
                (case_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def save_output(
        self,
        case_id: int,
        output_type: str,
        title: str,
        content: str,
    ) -> None:
        with self._connect() as connection:
            connection.execute(
                '''
                INSERT INTO case_outputs (
                    case_id, output_type, title, content
                )
                VALUES (?, ?, ?, ?)
                ''',
                (case_id, output_type, title, content),
            )

    def list_outputs(self, case_id: int) -> list[dict]:
        with self._connect() as connection:
            rows = connection.execute(
                '''
                SELECT * FROM case_outputs
                WHERE case_id = ?
                ORDER BY id DESC
                ''',
                (case_id,),
            ).fetchall()
        return [dict(row) for row in rows]
