from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any


class ResearchResultArchive:
    """Historial persistente de respuestas de IA, independiente del navegador."""

    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=30)
        connection.row_factory = sqlite3.Row
        connection.create_function(
            "lexia_casefold", 1,
            lambda value: str(value or "").casefold(),
        )
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA busy_timeout=30000")
        return connection

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS research_results (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_at TEXT NOT NULL,
                    kind TEXT NOT NULL CHECK(kind IN ('research', 'file')),
                    query TEXT NOT NULL,
                    title TEXT NOT NULL,
                    result TEXT NOT NULL,
                    model TEXT NOT NULL DEFAULT '',
                    response_id TEXT NOT NULL DEFAULT '',
                    input_tokens INTEGER NOT NULL DEFAULT 0,
                    output_tokens INTEGER NOT NULL DEFAULT 0,
                    total_tokens INTEGER NOT NULL DEFAULT 0,
                    source_count INTEGER NOT NULL DEFAULT 0,
                    document_count INTEGER NOT NULL DEFAULT 0
                )
                """
            )

    @staticmethod
    def _public(row: sqlite3.Row, include_result: bool) -> dict[str, Any]:
        item = dict(row)
        result = str(item.get("result", "") or "")
        if include_result:
            item["result"] = result
        else:
            item.pop("result", None)
            item["preview"] = " ".join(result.split())[:320]
        item["type_label"] = (
            "Investigación" if item.get("kind") == "research"
            else "Estudio de archivo"
        )
        return item

    def add(
        self,
        *,
        kind: str,
        query: str,
        title: str,
        result: str,
        model: str = "",
        response_id: str = "",
        input_tokens: int = 0,
        output_tokens: int = 0,
        total_tokens: int = 0,
        source_count: int = 0,
        document_count: int = 0,
    ) -> dict[str, Any]:
        if kind not in {"research", "file"}:
            raise ValueError("Tipo de resultado de investigación inválido.")
        clean_result = str(result or "").strip()
        if not clean_result:
            raise ValueError("No se puede guardar un resultado vacío.")
        created_at = datetime.now().isoformat(timespec="seconds")
        with self._connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO research_results (
                    created_at, kind, query, title, result, model, response_id,
                    input_tokens, output_tokens, total_tokens,
                    source_count, document_count
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    created_at, kind, str(query or "").strip(),
                    str(title or "Resultado de LexIA").strip(), clean_result,
                    str(model or ""), str(response_id or ""),
                    max(0, int(input_tokens or 0)),
                    max(0, int(output_tokens or 0)),
                    max(0, int(total_tokens or 0)),
                    max(0, int(source_count or 0)),
                    max(0, int(document_count or 0)),
                ),
            )
            record_id = int(cursor.lastrowid)
        return self.get(record_id)

    def list(self, limit: int = 50) -> list[dict[str, Any]]:
        safe_limit = max(1, min(int(limit or 50), 200))
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM research_results ORDER BY id DESC LIMIT ?",
                (safe_limit,),
            ).fetchall()
        return [self._public(row, include_result=False) for row in rows]

    def search(self, query: str, limit: int = 50) -> list[dict[str, Any]]:
        """Busca en título, consulta y respuesta completa sin exponerla en la lista."""
        clean_query = str(query or "").strip()
        if not clean_query:
            return self.list(limit)
        safe_limit = max(1, min(int(limit or 50), 200))
        folded_query = clean_query.casefold()
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM research_results
                WHERE instr(lexia_casefold(title), ?) > 0
                   OR instr(lexia_casefold(query), ?) > 0
                   OR instr(lexia_casefold(result), ?) > 0
                ORDER BY id DESC
                LIMIT ?
                """,
                (folded_query, folded_query, folded_query, safe_limit),
            ).fetchall()
        return [self._public(row, include_result=False) for row in rows]

    def delete(self, record_id: int) -> None:
        with self._connect() as connection:
            cursor = connection.execute(
                "DELETE FROM research_results WHERE id = ?",
                (int(record_id),),
            )
        if cursor.rowcount != 1:
            raise KeyError("El resultado solicitado no existe.")

    def get(self, record_id: int) -> dict[str, Any]:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM research_results WHERE id = ?",
                (int(record_id),),
            ).fetchone()
        if row is None:
            raise KeyError("El resultado solicitado no existe.")
        return self._public(row, include_result=True)
