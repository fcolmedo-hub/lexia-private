import sqlite3
from dataclasses import dataclass
from pathlib import Path

from config.settings import SETTINGS
from knowledge.extractor import DeterministicKnowledgeExtractor
from knowledge.planner import DeterministicLegalPlanner
from knowledge.ranker import DeterministicKnowledgeRanker
from knowledge.repository import KnowledgeRepository


@dataclass(slots=True)
class KnowledgeSyncResult:
    examined: int
    updated: int
    skipped: int
    removed: int
    errors: int


class KnowledgeEngine:
    """Motor local y determinista. No utiliza IA ni servicios externos."""

    def __init__(self, catalog_path=None, knowledge_path=None):
        self.catalog_path = Path(
            catalog_path or SETTINGS.catalog_path
        )
        self.repository = KnowledgeRepository(
            knowledge_path or SETTINGS.knowledge_path
        )
        self.extractor = DeterministicKnowledgeExtractor()
        self.planner = DeterministicLegalPlanner(
            self.repository,
            self.extractor,
        )
        self.ranker = DeterministicKnowledgeRanker(
            self.repository
        )

    def sync_incremental(
        self,
        progress_callback=None,
        rebuild_relations=True,
    ):
        documents = self._documents()
        active_paths = {
            row["path"]
            for row in documents
        }
        updated = skipped = errors = 0
        total = len(documents)

        for position, row in enumerate(
            documents,
            start=1,
        ):
            if progress_callback:
                progress_callback(
                    position - 1,
                    total,
                    row["path"],
                )

            try:
                if not self.repository.needs_update(
                    row["path"],
                    row["content_hash"],
                ):
                    skipped += 1
                else:
                    self.repository.save(
                        self.extractor.extract(
                            row["path"],
                            row["content_hash"],
                            row["name"],
                            row["category"],
                            row["text_content"],
                        )
                    )
                    updated += 1
            except Exception:
                errors += 1

            if progress_callback:
                progress_callback(
                    position,
                    total,
                    row["path"],
                )

        removed = self.repository.remove_missing(
            active_paths
        )

        if progress_callback:
            progress_callback(
                total,
                total,
                "Completado",
            )

        return KnowledgeSyncResult(
            total,
            updated,
            skipped,
            removed,
            errors,
        )

    def sync_paths(
        self,
        paths,
        deleted_paths=None,
        rebuild_relations=False,
        progress_callback=None,
    ):
        requested = {
            str(Path(path).resolve())
            for path in (paths or ())
            if path
        }
        deleted = {
            str(Path(path).resolve())
            for path in (deleted_paths or ())
            if path
        }

        requested -= deleted
        rows = self._documents_for_paths(
            requested
        )
        rows_by_path = {
            str(Path(row["path"]).resolve()): row
            for row in rows
        }

        updated = skipped = removed = errors = 0
        total = len(requested) + len(deleted)
        position = 0

        for path in sorted(deleted):
            if progress_callback:
                progress_callback(
                    position,
                    total,
                    path,
                )

            try:
                removed += self.repository.remove_path(
                    path
                )
            except Exception:
                errors += 1

            position += 1

            if progress_callback:
                progress_callback(
                    position,
                    total,
                    path,
                )

        for path in sorted(requested):
            if progress_callback:
                progress_callback(
                    position,
                    total,
                    path,
                )

            row = rows_by_path.get(path)

            try:
                if row is None:
                    removed += self.repository.remove_path(
                        path
                    )
                elif not self.repository.needs_update(
                    row["path"],
                    row["content_hash"],
                ):
                    skipped += 1
                else:
                    self.repository.save(
                        self.extractor.extract(
                            row["path"],
                            row["content_hash"],
                            row["name"],
                            row["category"],
                            row["text_content"],
                        )
                    )
                    updated += 1
            except Exception:
                errors += 1

            position += 1

            if progress_callback:
                progress_callback(
                    position,
                    total,
                    path,
                )

        if progress_callback:
            progress_callback(
                total,
                total,
                "Completado",
            )

        return KnowledgeSyncResult(
            examined=total,
            updated=updated,
            skipped=skipped,
            removed=removed,
            errors=errors,
        )

    def sync_document(
        self,
        path,
        rebuild_relations=False,
    ):
        return self.sync_paths(
            [path],
            rebuild_relations=rebuild_relations,
        )

    def move_document(
        self,
        old_path,
        new_path,
    ):
        return self.repository.move_path(
            str(Path(old_path).resolve()),
            str(Path(new_path).resolve()),
        )


    # >>> LEXIA KNOWLEDGE RELOCATION BATCH 1.0.1
    def move_documents(self, relocations):
        normalized = [
            (
                str(Path(old_path).resolve()),
                str(Path(new_path).resolve()),
            )
            for old_path, new_path in relocations
        ]
        return self.repository.move_paths(normalized)
    # <<< LEXIA KNOWLEDGE RELOCATION BATCH 1.0.1

    def rebuild_all_relations(self):
        self.repository.rebuild_relations()

    def _documents_for_paths(self, paths):
        if not paths:
            return []

        placeholders = ",".join(
            "?"
            for _ in paths
        )
        connection = sqlite3.connect(
            self.catalog_path
        )
        connection.row_factory = sqlite3.Row

        try:
            return connection.execute(
                f"""
                SELECT
                    path,
                    name,
                    category,
                    content_hash,
                    text_content
                FROM documents
                WHERE is_deleted = 0
                  AND duplicate_of IS NULL
                  AND extraction_error IS NULL
                  AND text_content != ''
                  AND path IN ({placeholders})
                """,
                tuple(paths),
            ).fetchall()
        finally:
            connection.close()

    def plan(self, query, interpretation):
        return self.planner.plan(
            query,
            interpretation,
        )

    def rank_sources(
        self,
        results,
        plan,
        limit,
    ):
        return self.ranker.rank(
            results,
            plan,
            limit,
        )

    def stats(self):
        return self.repository.stats()

    def citation_graph_stats(self):
        return self.repository.citation_graph_stats()

    def citation_graph_outgoing(self, path, limit=50):
        return self.repository.citation_graph_outgoing(path, limit)

    def citation_graph_incoming(self, path, limit=50):
        return self.repository.citation_graph_incoming(path, limit)

    def most_cited_documents(self, limit=25):
        return self.repository.most_cited_documents(limit)

    def _documents(self):
        connection = sqlite3.connect(
            self.catalog_path
        )
        connection.row_factory = sqlite3.Row

        try:
            return connection.execute(
                """
                SELECT
                    path,
                    name,
                    category,
                    content_hash,
                    text_content
                FROM documents
                WHERE is_deleted = 0
                  AND duplicate_of IS NULL
                  AND extraction_error IS NULL
                  AND text_content != ''
                ORDER BY path
                """
            ).fetchall()
        finally:
            connection.close()
