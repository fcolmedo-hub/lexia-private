import sqlite3
from pathlib import Path


class SearchFeedbackRepository:
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
                CREATE TABLE IF NOT EXISTS search_feedback (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    query TEXT NOT NULL,
                    document_path TEXT NOT NULL,
                    fragment_index INTEGER NOT NULL,
                    rating INTEGER NOT NULL CHECK (rating IN (-1, 1)),
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );

                CREATE INDEX IF NOT EXISTS idx_feedback_result
                ON search_feedback(document_path, fragment_index);
                '''
            )

    def add(
        self,
        query: str,
        document_path: str,
        fragment_index: int,
        rating: int,
    ) -> None:
        if rating not in (-1, 1):
            raise ValueError("rating debe ser -1 o 1.")

        with self._connect() as connection:
            connection.execute(
                '''
                INSERT INTO search_feedback (
                    query, document_path, fragment_index, rating
                )
                VALUES (?, ?, ?, ?)
                ''',
                (
                    query.strip(),
                    document_path,
                    fragment_index,
                    rating,
                ),
            )

    def aggregate_scores(
        self,
        keys: list[tuple[str, int]],
    ) -> dict[tuple[str, int], float]:
        if not keys:
            return {}

        scores: dict[tuple[str, int], float] = {}

        with self._connect() as connection:
            for path, fragment_index in keys:
                row = connection.execute(
                    '''
                    SELECT COALESCE(SUM(rating), 0) AS score
                    FROM search_feedback
                    WHERE document_path = ?
                      AND fragment_index = ?
                    ''',
                    (path, fragment_index),
                ).fetchone()

                raw = float(row["score"])
                scores[(path, fragment_index)] = max(
                    -0.08,
                    min(0.08, raw * 0.015),
                )

        return scores
