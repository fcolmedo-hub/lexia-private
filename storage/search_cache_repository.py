import json
import sqlite3
import time
from pathlib import Path

from config.settings import SETTINGS


class SearchCacheRepository:
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
                CREATE TABLE IF NOT EXISTS search_cache (
                    cache_key TEXT PRIMARY KEY,
                    payload_json TEXT NOT NULL,
                    created_at REAL NOT NULL
                );
                '''
            )

    def get(self, cache_key: str) -> list[dict] | None:
        with self._connect() as connection:
            row = connection.execute(
                '''
                SELECT payload_json, created_at
                FROM search_cache
                WHERE cache_key = ?
                ''',
                (cache_key,),
            ).fetchone()

        if not row:
            return None

        if time.time() - float(row["created_at"]) > SETTINGS.search_cache_ttl_seconds:
            self.delete(cache_key)
            return None

        return json.loads(row["payload_json"])

    def set(self, cache_key: str, payload: list[dict]) -> None:
        with self._connect() as connection:
            connection.execute(
                '''
                INSERT INTO search_cache (
                    cache_key, payload_json, created_at
                )
                VALUES (?, ?, ?)
                ON CONFLICT(cache_key) DO UPDATE SET
                    payload_json = excluded.payload_json,
                    created_at = excluded.created_at
                ''',
                (
                    cache_key,
                    json.dumps(payload, ensure_ascii=False),
                    time.time(),
                ),
            )
            connection.execute(
                '''
                DELETE FROM search_cache
                WHERE cache_key NOT IN (
                    SELECT cache_key
                    FROM search_cache
                    ORDER BY created_at DESC
                    LIMIT ?
                )
                ''',
                (SETTINGS.search_cache_max_entries,),
            )

    def delete(self, cache_key: str) -> None:
        with self._connect() as connection:
            connection.execute(
                "DELETE FROM search_cache WHERE cache_key = ?",
                (cache_key,),
            )

    def clear(self) -> None:
        with self._connect() as connection:
            connection.execute("DELETE FROM search_cache")

    def stats(self) -> dict[str, int]:
        with self._connect() as connection:
            count = connection.execute(
                "SELECT COUNT(*) AS total FROM search_cache"
            ).fetchone()["total"]

        return {"entries": int(count)}
