import sqlite3
from pathlib import Path


class LegalMatrixRepository:
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
                CREATE TABLE IF NOT EXISTS legal_matrix_rows (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    case_id INTEGER,
                    fact TEXT NOT NULL,
                    evidence TEXT NOT NULL DEFAULT '',
                    legal_rule TEXT NOT NULL DEFAULT '',
                    source TEXT NOT NULL DEFAULT '',
                    risk TEXT NOT NULL DEFAULT '',
                    status TEXT NOT NULL DEFAULT 'Pendiente',
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                '''
            )

    def add(
        self,
        fact: str,
        evidence: str = "",
        legal_rule: str = "",
        source: str = "",
        risk: str = "",
        status: str = "Pendiente",
        case_id: int | None = None,
    ) -> int:
        with self._connect() as connection:
            cursor = connection.execute(
                '''
                INSERT INTO legal_matrix_rows (
                    case_id, fact, evidence, legal_rule,
                    source, risk, status
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ''',
                (
                    case_id,
                    fact.strip(),
                    evidence.strip(),
                    legal_rule.strip(),
                    source.strip(),
                    risk.strip(),
                    status.strip(),
                ),
            )
            return int(cursor.lastrowid)

    def list_rows(
        self,
        case_id: int | None = None,
    ) -> list[dict]:
        sql = "SELECT * FROM legal_matrix_rows"
        params: list[object] = []

        if case_id is not None:
            sql += " WHERE case_id = ?"
            params.append(case_id)

        sql += " ORDER BY id"

        with self._connect() as connection:
            rows = connection.execute(
                sql,
                params,
            ).fetchall()

        return [dict(row) for row in rows]

    def delete(self, row_id: int) -> None:
        with self._connect() as connection:
            connection.execute(
                "DELETE FROM legal_matrix_rows WHERE id = ?",
                (row_id,),
            )
