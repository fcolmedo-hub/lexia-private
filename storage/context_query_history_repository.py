import sqlite3
from pathlib import Path


class ContextQueryHistoryRepository:
    def __init__(self, database_path: str | Path):
        self.database_path = Path(database_path)
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path, timeout=15)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS context_query_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    query TEXT NOT NULL,
                    facts TEXT NOT NULL DEFAULT '',
                    objective TEXT NOT NULL,
                    additional_instruction TEXT NOT NULL DEFAULT '',
                    max_sources INTEGER NOT NULL DEFAULT 14,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )

    def save(
        self,
        query: str,
        facts: str,
        objective: str,
        additional_instruction: str,
        max_sources: int,
    ) -> int:
        clean_query = str(query or "").strip()
        if not clean_query:
            raise ValueError("La consulta no puede estar vacía.")

        with self._connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO context_query_history (
                    query, facts, objective,
                    additional_instruction, max_sources
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (
                    clean_query,
                    str(facts or ""),
                    str(objective or ""),
                    str(additional_instruction or ""),
                    int(max_sources),
                ),
            )
            return int(cursor.lastrowid)

    def list_recent(
        self,
        limit: int = 100,
        search: str = "",
    ) -> list[dict]:
        clean = str(search or "").strip()
        sql = """
            SELECT id, query, facts, objective,
                   additional_instruction, max_sources, created_at
            FROM context_query_history
        """
        params: list[object] = []

        if clean:
            pattern = f"%{clean}%"
            sql += """
                WHERE query LIKE ? COLLATE NOCASE
                   OR facts LIKE ? COLLATE NOCASE
                   OR additional_instruction LIKE ? COLLATE NOCASE
            """
            params.extend([pattern, pattern, pattern])

        sql += """
            ORDER BY datetime(created_at) DESC, id DESC
            LIMIT ?
        """
        params.append(int(limit))

        with self._connect() as connection:
            rows = connection.execute(sql, params).fetchall()

        return [dict(row) for row in rows]

    def get(self, history_id: int) -> dict | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT id, query, facts, objective,
                       additional_instruction, max_sources, created_at
                FROM context_query_history
                WHERE id = ?
                """,
                (int(history_id),),
            ).fetchone()
        return dict(row) if row else None

    def delete(self, history_id: int) -> bool:
        with self._connect() as connection:
            cursor = connection.execute(
                "DELETE FROM context_query_history WHERE id = ?",
                (int(history_id),),
            )
        return cursor.rowcount > 0

    def count(self) -> int:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT COUNT(*) AS total FROM context_query_history"
            ).fetchone()
        return int(row["total"] or 0)
