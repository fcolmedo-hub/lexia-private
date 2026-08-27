from __future__ import annotations

import json
import logging
import sqlite3
from pathlib import Path

from config.settings import SETTINGS
from services.library_classification_tree import LibraryClassificationTree
from storage.jurisprudence_audit import write_jurisprudence_audit
from storage.jurisprudence_content_indexer import update_content_index
from storage.jurisprudence_index import rebuild_structural_index


def _resolve_under_root(root: Path, value) -> Path:
    p = Path(value)
    return p if p.is_absolute() else (root / p).resolve()


class ClassificationShadowSync:
    """Synchronize path-derived classification metadata after AutoSync.

    The shadow columns remain independent from FTS/Qdrant/Knowledge. Once the
    catalog transaction is closed, the jurisprudence side-index is refreshed
    as a separate best-effort layer. A failure there never rolls back normal
    library synchronization.
    """

    _SHADOW_COLUMNS = {
        "relative_path": "TEXT",
        "folder_category": "TEXT",
        "classification_1": "TEXT",
        "classification_2": "TEXT",
        "classification_3": "TEXT",
        "classification_4": "TEXT",
        "classification_depth": "INTEGER NOT NULL DEFAULT 0",
        "classification_levels_json": "TEXT NOT NULL DEFAULT '[]'",
    }

    def __init__(self, project_root: str | Path):
        self.project_root = Path(project_root).resolve()
        self.catalog_path = _resolve_under_root(
            self.project_root, SETTINGS.catalog_path
        )
        self.library_root = _resolve_under_root(
            self.project_root, SETTINGS.library_path
        )
        self.logger = logging.getLogger("lexia.jurisprudence_autosync")

        aliases = None
        config_path = self.project_root / "config" / "library_tree.json"
        if config_path.exists():
            aliases = json.loads(
                config_path.read_text(encoding="utf-8")
            ).get("category_aliases")

        self.tree = LibraryClassificationTree(
            self.library_root,
            aliases,
        )

    @classmethod
    def _ensure_shadow_columns(cls, con: sqlite3.Connection) -> None:
        """Completa catálogos antiguos antes de escribir metadatos shadow."""
        existing = {
            str(row[1])
            for row in con.execute("PRAGMA table_info(documents)").fetchall()
        }
        for column, definition in cls._SHADOW_COLUMNS.items():
            if column in existing:
                continue
            con.execute(
                f"ALTER TABLE documents ADD COLUMN {column} {definition}"
            )

    def _refresh_jurisprudence_index(self) -> dict:
        """Best-effort refresh and audit after library synchronization cycles."""
        try:
            structural = rebuild_structural_index(self.catalog_path)
            legal = update_content_index(self.catalog_path)
            audit_path = write_jurisprudence_audit(self.catalog_path)
            result = {
                "structural": structural,
                "legal": legal,
                "audit_path": str(audit_path),
            }
            self.logger.info(
                "Jurisprudence AutoIndex | structural=%s | legal=%s | audit=%s",
                structural,
                legal,
                audit_path,
            )
            return result
        except Exception:
            self.logger.exception("Jurisprudence AutoIndex falló")
            return {"error": True}

    def update_paths(self, paths) -> dict:
        normalized = []
        seen = set()
        for value in paths or []:
            if not value:
                continue
            resolved = str(Path(value).resolve())
            if resolved not in seen:
                seen.add(resolved)
                normalized.append(resolved)

        # Even an empty path list can represent a deletion-only AutoSync cycle.
        # Rebuilding the small side-index also removes stale jurisprudence rows.
        if not normalized:
            jurisprudence = self._refresh_jurisprudence_index()
            return {
                "requested": 0,
                "updated": 0,
                "missing": 0,
                "invalid": 0,
                "jurisprudence": jurisprudence,
            }

        con = sqlite3.connect(self.catalog_path)
        con.row_factory = sqlite3.Row
        updated = 0
        missing = 0
        invalid = 0
        try:
            self._ensure_shadow_columns(con)
            con.execute("BEGIN")
            for path in normalized:
                row = con.execute(
                    """
                    SELECT path
                    FROM documents
                    WHERE path = ? AND COALESCE(is_deleted,0)=0
                    """,
                    (path,),
                ).fetchone()

                if not row:
                    missing += 1
                    continue

                projected = self.tree.classify(path)
                if not projected.valid:
                    invalid += 1
                    continue

                # Physical Category Authority 1.0:
                # category/folder_category deben conservar literalmente
                # el primer nivel físico del árbol (ej. Legislacion).
                from services.structural_category_policy import (
                    classify_structural_path,
                )
                structural = classify_structural_path(path)

                con.execute(
                    """
                    UPDATE documents
                    SET relative_path = ?,
                        category = ?,
                        folder_category = ?,
                        classification_1 = ?,
                        classification_2 = ?,
                        classification_3 = ?,
                        classification_4 = ?,
                        classification_depth = ?,
                        classification_levels_json = ?
                    WHERE path = ?
                    """,
                    (
                        projected.relative_path,
                        structural.category,
                        structural.category,
                        projected.classification_1,
                        projected.classification_2,
                        projected.classification_3,
                        projected.classification_4,
                        len(projected.levels),
                        json.dumps(
                            list(projected.levels),
                            ensure_ascii=False,
                        ),
                        path,
                    ),
                )
                updated += 1
            con.commit()
        except Exception:
            con.rollback()
            raise
        finally:
            con.close()

        jurisprudence = self._refresh_jurisprudence_index()
        return {
            "requested": len(normalized),
            "updated": updated,
            "missing": missing,
            "invalid": invalid,
            "jurisprudence": jurisprudence,
        }
