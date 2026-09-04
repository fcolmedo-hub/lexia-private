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
                    authority TEXT NOT NULL DEFAULT '',
                    file_number TEXT NOT NULL DEFAULT '',
                    parties TEXT NOT NULL DEFAULT '',
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

                CREATE TABLE IF NOT EXISTS case_nodes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    case_id INTEGER NOT NULL,
                    parent_id INTEGER,
                    node_kind TEXT NOT NULL,
                    title TEXT NOT NULL,
                    adversary_text TEXT NOT NULL DEFAULT '',
                    own_position TEXT NOT NULL DEFAULT '',
                    primary_document_id INTEGER,
                    sort_order INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS case_node_sources (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    case_id INTEGER NOT NULL,
                    node_id INTEGER NOT NULL,
                    case_document_id INTEGER,
                    case_entry_id INTEGER,
                    stance TEXT NOT NULL DEFAULT 'fundamento',
                    note TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    CHECK (case_document_id IS NOT NULL OR case_entry_id IS NOT NULL),
                    UNIQUE(node_id, case_document_id, case_entry_id)
                );

                CREATE INDEX IF NOT EXISTS idx_case_documents_case
                    ON case_documents(case_id, category, created_at DESC);
                CREATE INDEX IF NOT EXISTS idx_case_entries_case
                    ON case_entries(case_id, created_at ASC, id ASC);
                CREATE INDEX IF NOT EXISTS idx_case_nodes_case
                    ON case_nodes(case_id, parent_id, sort_order, id);
                CREATE INDEX IF NOT EXISTS idx_case_node_sources_node
                    ON case_node_sources(node_id, id);
                '''
            )

            # Bases de Casos creadas antes de esta versión no tienen estos
            # datos de identificación. SQLite no admite ADD COLUMN IF NOT EXISTS.
            columns = {row["name"] for row in connection.execute("PRAGMA table_info(cases)")}
            for name in ("authority", "file_number", "parties"):
                if name not in columns:
                    connection.execute(
                        f"ALTER TABLE cases ADD COLUMN {name} TEXT NOT NULL DEFAULT ''"
                    )

    def create_case(
        self,
        name: str,
        description: str = "",
        *,
        authority: str = "",
        file_number: str = "",
        parties: str = "",
    ) -> int:
        with self._connect() as connection:
            cursor = connection.execute(
                '''
                INSERT INTO cases (name, description, authority, file_number, parties)
                VALUES (?, ?, ?, ?, ?)
                ''',
                (
                    name.strip(), description.strip(), authority.strip(),
                    file_number.strip(), parties.strip(),
                ),
            )
            return int(cursor.lastrowid)

    def list_cases(self) -> list[dict]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM cases ORDER BY updated_at DESC, id DESC"
            ).fetchall()
        return [dict(row) for row in rows]

    def update_case(
        self,
        case_id: int,
        name: str,
        description: str = "",
        *,
        authority: str = "",
        file_number: str = "",
        parties: str = "",
    ) -> None:
        name = str(name or "").strip()
        if not name:
            raise ValueError("Indicá el nombre o carátula del caso.")
        with self._connect() as connection:
            cursor = connection.execute(
                '''
                UPDATE cases
                SET name = ?, description = ?, authority = ?, file_number = ?,
                    parties = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                ''',
                (
                    name, str(description or "").strip(), str(authority or "").strip(),
                    str(file_number or "").strip(), str(parties or "").strip(), int(case_id),
                ),
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
            for table in (
                "case_node_sources", "case_nodes", "case_documents", "case_entries",
                "case_sources", "case_outputs",
            ):
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

    def add_node(
        self,
        case_id: int,
        *,
        node_kind: str,
        title: str,
        parent_id: int | None = None,
        adversary_text: str = "",
        own_position: str = "",
        primary_document_id: int | None = None,
    ) -> int:
        """Create a principal procedural branch or a legal issue below it."""
        case_id = int(case_id)
        node_kind = str(node_kind or "").strip().lower()
        title = str(title or "").strip()
        if node_kind not in {"hito", "cuestion"}:
            raise ValueError("El tipo de rama debe ser hito o cuestión.")
        if not title:
            raise ValueError("Indicá el título de la rama o cuestión.")
        if node_kind == "hito":
            parent_id = None
        elif parent_id is None:
            raise ValueError("Toda cuestión debe pertenecer a una rama principal.")

        with self._connect() as connection:
            if connection.execute("SELECT 1 FROM cases WHERE id = ?", (case_id,)).fetchone() is None:
                raise KeyError(f"No existe el caso #{case_id}.")
            if parent_id is not None:
                parent = connection.execute(
                    "SELECT node_kind, case_id FROM case_nodes WHERE id = ?", (int(parent_id),)
                ).fetchone()
                if parent is None or int(parent["case_id"]) != case_id:
                    raise ValueError("La rama principal seleccionada no pertenece a este caso.")
            if primary_document_id is not None:
                document = connection.execute(
                    "SELECT 1 FROM case_documents WHERE id = ? AND case_id = ?",
                    (int(primary_document_id), case_id),
                ).fetchone()
                if document is None:
                    raise ValueError("El documento elegido no pertenece a este caso.")
            order = connection.execute(
                "SELECT COALESCE(MAX(sort_order), 0) + 1 AS value FROM case_nodes WHERE case_id = ? AND parent_id IS ?",
                (case_id, parent_id),
            ).fetchone()["value"]
            cursor = connection.execute(
                '''
                INSERT INTO case_nodes (
                    case_id, parent_id, node_kind, title, adversary_text,
                    own_position, primary_document_id, sort_order
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''',
                (
                    case_id, parent_id, node_kind, title, str(adversary_text or "").strip(),
                    str(own_position or "").strip(), primary_document_id, order,
                ),
            )
            connection.execute(
                "UPDATE cases SET updated_at = CURRENT_TIMESTAMP WHERE id = ?", (case_id,)
            )
            return int(cursor.lastrowid)

    def update_node(
        self,
        case_id: int,
        node_id: int,
        *,
        title: str,
        adversary_text: str = "",
        own_position: str = "",
        primary_document_id: int | None = None,
    ) -> None:
        title = str(title or "").strip()
        if not title:
            raise ValueError("Indicá el título de la rama o cuestión.")
        with self._connect() as connection:
            if primary_document_id is not None and connection.execute(
                "SELECT 1 FROM case_documents WHERE id = ? AND case_id = ?",
                (int(primary_document_id), int(case_id)),
            ).fetchone() is None:
                raise ValueError("El documento elegido no pertenece a este caso.")
            cursor = connection.execute(
                '''
                UPDATE case_nodes
                SET title = ?, adversary_text = ?, own_position = ?,
                    primary_document_id = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ? AND case_id = ?
                ''',
                (
                    title, str(adversary_text or "").strip(), str(own_position or "").strip(),
                    primary_document_id, int(node_id), int(case_id),
                ),
            )
            if cursor.rowcount != 1:
                raise KeyError(f"No existe la rama #{node_id} en este caso.")
            connection.execute(
                "UPDATE cases SET updated_at = CURRENT_TIMESTAMP WHERE id = ?", (int(case_id),)
            )

    def delete_node(self, case_id: int, node_id: int) -> None:
        """Delete a branch and all its questions, never the library sources."""
        case_id, node_id = int(case_id), int(node_id)
        with self._connect() as connection:
            node = connection.execute(
                "SELECT id FROM case_nodes WHERE id = ? AND case_id = ?", (node_id, case_id)
            ).fetchone()
            if node is None:
                raise KeyError(f"No existe la rama #{node_id} en este caso.")
            ids = [node_id]
            index = 0
            while index < len(ids):
                rows = connection.execute(
                    "SELECT id FROM case_nodes WHERE parent_id = ? AND case_id = ?", (ids[index], case_id)
                ).fetchall()
                ids.extend(int(row["id"]) for row in rows)
                index += 1
            markers = ",".join("?" for _ in ids)
            connection.execute(f"DELETE FROM case_node_sources WHERE node_id IN ({markers})", ids)
            connection.execute(f"DELETE FROM case_nodes WHERE id IN ({markers})", ids)
            connection.execute(
                "UPDATE cases SET updated_at = CURRENT_TIMESTAMP WHERE id = ?", (case_id,)
            )

    def add_node_source(
        self,
        case_id: int,
        node_id: int,
        *,
        case_document_id: int | None = None,
        case_entry_id: int | None = None,
        stance: str = "fundamento",
        note: str = "",
    ) -> int:
        if case_document_id is None and case_entry_id is None:
            raise ValueError("Elegí un documento o un fragmento para vincular.")
        case_id, node_id = int(case_id), int(node_id)
        with self._connect() as connection:
            if connection.execute(
                "SELECT 1 FROM case_nodes WHERE id = ? AND case_id = ?", (node_id, case_id)
            ).fetchone() is None:
                raise KeyError(f"No existe la rama #{node_id} en este caso.")
            if case_document_id is not None and connection.execute(
                "SELECT 1 FROM case_documents WHERE id = ? AND case_id = ?", (int(case_document_id), case_id)
            ).fetchone() is None:
                raise ValueError("El documento no pertenece a este caso.")
            if case_entry_id is not None and connection.execute(
                "SELECT 1 FROM case_entries WHERE id = ? AND case_id = ?", (int(case_entry_id), case_id)
            ).fetchone() is None:
                raise ValueError("El fragmento no pertenece a este caso.")
            existing = connection.execute(
                '''
                SELECT 1 FROM case_node_sources
                WHERE node_id = ?
                  AND ((case_document_id = ?) OR (case_document_id IS NULL AND ? IS NULL))
                  AND ((case_entry_id = ?) OR (case_entry_id IS NULL AND ? IS NULL))
                ''',
                (node_id, case_document_id, case_document_id, case_entry_id, case_entry_id),
            ).fetchone()
            if existing is not None:
                raise ValueError("Esa fuente ya está vinculada a esta cuestión.")
            cursor = connection.execute(
                '''
                INSERT INTO case_node_sources (
                    case_id, node_id, case_document_id, case_entry_id, stance, note
                ) VALUES (?, ?, ?, ?, ?, ?)
                ''',
                (
                    case_id, node_id, case_document_id, case_entry_id,
                    str(stance or "fundamento").strip(), str(note or "").strip(),
                ),
            )
            connection.execute(
                "UPDATE cases SET updated_at = CURRENT_TIMESTAMP WHERE id = ?", (case_id,)
            )
            return int(cursor.lastrowid)

    def delete_node_source(self, case_id: int, source_id: int) -> None:
        with self._connect() as connection:
            cursor = connection.execute(
                "DELETE FROM case_node_sources WHERE id = ? AND case_id = ?",
                (int(source_id), int(case_id)),
            )
            if cursor.rowcount != 1:
                raise KeyError(f"No existe el vínculo de fuente #{source_id}.")
            connection.execute(
                "UPDATE cases SET updated_at = CURRENT_TIMESTAMP WHERE id = ?", (int(case_id),)
            )

    def list_nodes(self, case_id: int) -> list[dict]:
        with self._connect() as connection:
            rows = connection.execute(
                '''
                SELECT n.*, d.document_name AS primary_document_name,
                       d.document_path AS primary_document_path
                FROM case_nodes n
                LEFT JOIN case_documents d ON d.id = n.primary_document_id
                WHERE n.case_id = ?
                ORDER BY n.parent_id IS NOT NULL, n.parent_id, n.sort_order, n.id
                ''',
                (int(case_id),),
            ).fetchall()
            sources = connection.execute(
                '''
                SELECT s.id, s.node_id, s.stance, s.note,
                       d.id AS document_id, d.document_name, d.document_path,
                       d.category, e.id AS entry_id, e.title AS entry_title,
                       e.content AS entry_content, e.source_excerpt, e.page_start,
                       e.document_name AS entry_document_name, e.document_path AS entry_document_path
                FROM case_node_sources s
                LEFT JOIN case_documents d ON d.id = s.case_document_id
                LEFT JOIN case_entries e ON e.id = s.case_entry_id
                WHERE s.case_id = ?
                ORDER BY s.id ASC
                ''',
                (int(case_id),),
            ).fetchall()
        output = [dict(row) for row in rows]
        by_node = {item["id"]: item for item in output}
        for item in output:
            item["sources"] = []
            item["children"] = []
        for row in sources:
            source = dict(row)
            if source["node_id"] in by_node:
                by_node[source["node_id"]]["sources"].append(source)
        roots: list[dict] = []
        for item in output:
            if item["parent_id"] is None:
                roots.append(item)
            elif item["parent_id"] in by_node:
                by_node[item["parent_id"]]["children"].append(item)
        return roots

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
            "nodes": self.list_nodes(case_id),
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
