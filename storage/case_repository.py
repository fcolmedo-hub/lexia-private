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

                CREATE TABLE IF NOT EXISTS case_documents (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    case_id INTEGER NOT NULL,
                    document_id INTEGER,
                    document_name TEXT NOT NULL,
                    document_path TEXT NOT NULL,
                    category TEXT NOT NULL DEFAULT '',
                    relation_kind TEXT NOT NULL DEFAULT 'vinculado',
                    note TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(case_id, document_path)
                );

                CREATE TABLE IF NOT EXISTS case_entries (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    case_id INTEGER NOT NULL,
                    entry_type TEXT NOT NULL,
                    title TEXT NOT NULL DEFAULT '',
                    content TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'vigente',
                    document_id INTEGER,
                    document_name TEXT NOT NULL DEFAULT '',
                    document_path TEXT NOT NULL DEFAULT '',
                    page_start INTEGER,
                    page_end INTEGER,
                    source_excerpt TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );

                CREATE INDEX IF NOT EXISTS idx_case_documents_case
                    ON case_documents(case_id, category, created_at DESC);
                CREATE INDEX IF NOT EXISTS idx_case_entries_case
                    ON case_entries(case_id, created_at ASC, id ASC);
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

    def update_case(self, case_id: int, name: str, description: str = "") -> None:
        name = str(name or "").strip()
        if not name:
            raise ValueError("Indicá el nombre o carátula del caso.")
        with self._connect() as connection:
            cursor = connection.execute(
                '''
                UPDATE cases
                SET name = ?, description = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                ''',
                (name, str(description or "").strip(), int(case_id)),
            )
            if cursor.rowcount != 1:
                raise KeyError(f"No existe el caso #{case_id}.")

    def delete_case(self, case_id: int) -> None:
        """Delete one local case and its local links, never library documents."""
        case_id = int(case_id)
        with self._connect() as connection:
            exists = connection.execute(
                "SELECT 1 FROM cases WHERE id = ?", (case_id,)
            ).fetchone()
            if exists is None:
                raise KeyError(f"No existe el caso #{case_id}.")
            for table in ("case_documents", "case_entries", "case_sources", "case_outputs"):
                connection.execute(f"DELETE FROM {table} WHERE case_id = ?", (case_id,))
            connection.execute("DELETE FROM cases WHERE id = ?", (case_id,))

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

    def link_document(
        self,
        case_id: int,
        *,
        document_name: str,
        document_path: str,
        category: str = "",
        document_id: int | None = None,
        relation_kind: str = "vinculado",
        note: str = "",
    ) -> int:
        """Link an indexed document to a case without copying its contents."""
        document_path = str(document_path or "").strip()
        if not document_path:
            raise ValueError("El documento vinculado debe conservar su ruta.")
        with self._connect() as connection:
            connection.execute(
                '''
                INSERT INTO case_documents (
                    case_id, document_id, document_name, document_path,
                    category, relation_kind, note
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(case_id, document_path) DO UPDATE SET
                    document_id = excluded.document_id,
                    document_name = excluded.document_name,
                    category = excluded.category,
                    relation_kind = excluded.relation_kind,
                    note = excluded.note
                ''',
                (
                    case_id, document_id, document_name.strip(), document_path,
                    category.strip(), relation_kind.strip() or "vinculado",
                    note.strip(),
                ),
            )
            row = connection.execute(
                "SELECT id FROM case_documents WHERE case_id = ? AND document_path = ?",
                (case_id, document_path),
            ).fetchone()
            connection.execute(
                "UPDATE cases SET updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (case_id,),
            )
        return int(row["id"])

    def list_documents(self, case_id: int, category: str | None = None) -> list[dict]:
        query = "SELECT * FROM case_documents WHERE case_id = ?"
        values: list[object] = [case_id]
        if category is not None:
            query += " AND category = ?"
            values.append(category)
        query += " ORDER BY category COLLATE NOCASE, created_at DESC, id DESC"
        with self._connect() as connection:
            rows = connection.execute(query, values).fetchall()
        return [dict(row) for row in rows]

    def add_entry(
        self,
        case_id: int,
        *,
        entry_type: str,
        content: str,
        title: str = "",
        status: str = "vigente",
        document_id: int | None = None,
        document_name: str = "",
        document_path: str = "",
        page_start: int | None = None,
        page_end: int | None = None,
        source_excerpt: str = "",
    ) -> int:
        """Append a traceable bitácora entry to a case."""
        entry_type = entry_type.strip()
        content = content.strip()
        if not entry_type:
            raise ValueError("La entrada debe tener un tipo.")
        if not content:
            raise ValueError("La entrada no puede estar vacía.")
        with self._connect() as connection:
            cursor = connection.execute(
                '''
                INSERT INTO case_entries (
                    case_id, entry_type, title, content, status,
                    document_id, document_name, document_path,
                    page_start, page_end, source_excerpt
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''',
                (
                    case_id, entry_type, title.strip(), content,
                    status.strip() or "vigente", document_id,
                    document_name.strip(), document_path.strip(),
                    page_start, page_end, source_excerpt.strip(),
                ),
            )
            connection.execute(
                "UPDATE cases SET updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (case_id,),
            )
            return int(cursor.lastrowid)

    def list_entries(self, case_id: int, limit: int | None = None) -> list[dict]:
        query = "SELECT * FROM case_entries WHERE case_id = ? ORDER BY created_at ASC, id ASC"
        values: list[object] = [case_id]
        if limit is not None:
            query += " LIMIT ?"
            values.append(max(1, int(limit)))
        with self._connect() as connection:
            rows = connection.execute(query, values).fetchall()
        return [dict(row) for row in rows]

    def case_snapshot(self, case_id: int) -> dict:
        """Return the local, auditable package on which an AI opinion may later rely."""
        with self._connect() as connection:
            case = connection.execute(
                "SELECT * FROM cases WHERE id = ?", (case_id,)
            ).fetchone()
        if case is None:
            raise KeyError(f"No existe el caso #{case_id}.")
        return {
            "case": dict(case),
            "documents": self.list_documents(case_id),
            "entries": self.list_entries(case_id),
            "outputs": self.list_outputs(case_id),
        }

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
