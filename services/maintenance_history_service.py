from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
import sqlite3
import threading

from config.settings import SETTINGS


class MaintenanceHistoryService:
    """Small bounded audit log for explicit Maintenance actions."""

    def __init__(
        self,
        database_path: str | Path | None = None,
        retention: int = 500,
    ):
        self.database_path = Path(
            database_path
            or (SETTINGS.runtime_path / "maintenance_history.sqlite3")
        )
        self.retention = max(50, int(retention))
        self._lock = threading.RLock()
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path, timeout=5)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS maintenance_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_at TEXT NOT NULL,
                    action TEXT NOT NULL,
                    status TEXT NOT NULL,
                    message TEXT NOT NULL,
                    details_json TEXT NOT NULL DEFAULT '{}'
                )
                """
            )
            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS
                idx_maintenance_history_created
                ON maintenance_history(id DESC)
                """
            )

    def record(
        self,
        action: str,
        status: str,
        message: str,
        details: dict | None = None,
    ) -> None:
        payload = json.dumps(
            details or {},
            ensure_ascii=False,
            default=str,
        )
        with self._lock, self._connect() as connection:
            connection.execute(
                """
                INSERT INTO maintenance_history (
                    created_at, action, status, message, details_json
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (
                    datetime.now().isoformat(timespec="seconds"),
                    str(action or "unknown"),
                    str(status or "ok"),
                    str(message or ""),
                    payload,
                ),
            )
            connection.execute(
                """
                DELETE FROM maintenance_history
                WHERE id NOT IN (
                    SELECT id
                    FROM maintenance_history
                    ORDER BY id DESC
                    LIMIT ?
                )
                """,
                (self.retention,),
            )

    def recent(self, limit: int = 8) -> list[dict]:
        safe_limit = max(1, min(100, int(limit)))
        with self._lock, self._connect() as connection:
            rows = connection.execute(
                """
                SELECT created_at, action, status, message, details_json
                FROM maintenance_history
                ORDER BY id DESC
                LIMIT ?
                """,
                (safe_limit,),
            ).fetchall()
        result = []
        for row in rows:
            try:
                details = json.loads(row["details_json"] or "{}")
            except (TypeError, ValueError):
                details = {}
            result.append({
                "created_at": row["created_at"],
                "action": row["action"],
                "status": row["status"],
                "message": row["message"],
                "details": details,
            })
        return result
