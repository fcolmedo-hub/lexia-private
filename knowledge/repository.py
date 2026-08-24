from __future__ import annotations

import sqlite3
from pathlib import Path

from knowledge.extractor import KnowledgeDocument


class KnowledgeRepository:
    """Índice SQLite de señales del Knowledge Engine."""

    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self):
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS knowledge_documents (
                    path TEXT PRIMARY KEY,
                    content_hash TEXT NOT NULL,
                    name TEXT NOT NULL,
                    category TEXT NOT NULL,
                    concepts TEXT NOT NULL DEFAULT '',
                    cited_rules TEXT NOT NULL DEFAULT '',
                    authorities TEXT NOT NULL DEFAULT '',
                    jurisdictions TEXT NOT NULL DEFAULT '',
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE IF NOT EXISTS knowledge_relations (
                    source_path TEXT NOT NULL,
                    target_path TEXT NOT NULL,
                    relation_type TEXT NOT NULL,
                    PRIMARY KEY (source_path, target_path, relation_type)
                );
                CREATE INDEX IF NOT EXISTS idx_knowledge_relations_target
                    ON knowledge_relations(target_path);
                """
            )

    def needs_update(self, path, content_hash) -> bool:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT content_hash FROM knowledge_documents WHERE path = ?", (str(path),)
            ).fetchone()
        return row is None or row["content_hash"] != str(content_hash or "")

    def save(self, document: KnowledgeDocument) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO knowledge_documents (
                    path, content_hash, name, category, concepts, cited_rules, authorities, jurisdictions, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(path) DO UPDATE SET
                    content_hash=excluded.content_hash, name=excluded.name, category=excluded.category,
                    concepts=excluded.concepts, cited_rules=excluded.cited_rules,
                    authorities=excluded.authorities, jurisdictions=excluded.jurisdictions,
                    updated_at=CURRENT_TIMESTAMP
                """,
                (
                    document.path, document.content_hash, document.name, document.category,
                    self._pack(document.concepts), self._pack(document.cited_rules),
                    self._pack(document.authorities), self._pack(document.jurisdictions),
                ),
            )

    def knowledge_for_path(self, path):
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM knowledge_documents WHERE path = ?", (str(path),)
            ).fetchone()
        if row is None:
            return None
        return {
            "path": row["path"], "content_hash": row["content_hash"], "name": row["name"],
            "category": row["category"], "concepts": self._unpack(row["concepts"]),
            "cited_rules": self._unpack(row["cited_rules"]),
            "authorities": self._unpack(row["authorities"]),
            "jurisdictions": self._unpack(row["jurisdictions"]), "updated_at": row["updated_at"],
        }

    def remove_path(self, path) -> int:
        path = str(path)
        with self._connect() as connection:
            connection.execute("DELETE FROM knowledge_relations WHERE source_path = ? OR target_path = ?", (path, path))
            return connection.execute("DELETE FROM knowledge_documents WHERE path = ?", (path,)).rowcount

    def remove_missing(self, active_paths) -> int:
        active = {str(path) for path in active_paths}
        with self._connect() as connection:
            rows = connection.execute("SELECT path FROM knowledge_documents").fetchall()
        return sum(self.remove_path(row["path"]) for row in rows if row["path"] not in active)

    def move_path(self, old_path, new_path) -> int:
        with self._connect() as connection:
            cursor = connection.execute("UPDATE knowledge_documents SET path = ?, updated_at=CURRENT_TIMESTAMP WHERE path = ?", (str(new_path), str(old_path)))
            connection.execute("UPDATE knowledge_relations SET source_path = ? WHERE source_path = ?", (str(new_path), str(old_path)))
            connection.execute("UPDATE knowledge_relations SET target_path = ? WHERE target_path = ?", (str(new_path), str(old_path)))
            return cursor.rowcount

    def move_paths(self, relocations) -> int:
        return sum(self.move_path(old_path, new_path) for old_path, new_path in relocations)

    def rebuild_relations(self) -> None:
        with self._connect() as connection:
            rows = connection.execute("SELECT path, cited_rules FROM knowledge_documents").fetchall()
            connection.execute("DELETE FROM knowledge_relations")
            for source in rows:
                rules = set(self._unpack(source["cited_rules"]))
                if not rules:
                    continue
                for target in rows:
                    if source["path"] == target["path"]:
                        continue
                    if rules.intersection(self._unpack(target["cited_rules"])):
                        connection.execute("INSERT OR IGNORE INTO knowledge_relations VALUES (?, ?, 'cita_compartida')", (source["path"], target["path"]))

    def stats(self):
        with self._connect() as connection:
            count = connection.execute("SELECT COUNT(*) FROM knowledge_documents").fetchone()[0]
        return {"documents": count, "indexed_documents": count}

    def citation_graph_stats(self):
        with self._connect() as connection:
            edges = connection.execute("SELECT COUNT(*) FROM knowledge_relations").fetchone()[0]
        return {"nodes": self.stats()["documents"], "edges": edges}

    def citation_graph_outgoing(self, path, limit=50):
        return self._relations("source_path", path, limit)

    def citation_graph_incoming(self, path, limit=50):
        return self._relations("target_path", path, limit)

    def most_cited_documents(self, limit=25):
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT target_path AS path, COUNT(*) AS citations FROM knowledge_relations GROUP BY target_path ORDER BY citations DESC, target_path LIMIT ?", (int(limit),)
            ).fetchall()
        return [dict(row) for row in rows]

    def _relations(self, field, path, limit):
        other = "target_path" if field == "source_path" else "source_path"
        with self._connect() as connection:
            rows = connection.execute(
                f"SELECT {other} AS path, relation_type FROM knowledge_relations WHERE {field} = ? LIMIT ?", (str(path), int(limit))
            ).fetchall()
        return [dict(row) for row in rows]

    @staticmethod
    def _pack(values):
        return "\x1f".join(str(value) for value in values if value)

    @staticmethod
    def _unpack(value):
        return [item for item in str(value or "").split("\x1f") if item]
