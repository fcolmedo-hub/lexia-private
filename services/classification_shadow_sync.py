from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from config.settings import SETTINGS
from services.library_classification_tree import LibraryClassificationTree


def _resolve_under_root(root: Path, value) -> Path:
    p = Path(value)
    return p if p.is_absolute() else (root / p).resolve()


class ClassificationShadowSync:
    """
    Mantiene exclusivamente los metadatos shadow derivados de la ruta.
    No toca category legacy, fragments, FTS, Qdrant ni Knowledge.
    """

    def __init__(self, project_root: str | Path):
        self.project_root = Path(project_root).resolve()
        self.catalog_path = _resolve_under_root(
            self.project_root, SETTINGS.catalog_path
        )
        self.library_root = _resolve_under_root(
            self.project_root, SETTINGS.library_path
        )

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

        if not normalized:
            return {"requested": 0, "updated": 0, "missing": 0, "invalid": 0}

        con = sqlite3.connect(self.catalog_path)
        con.row_factory = sqlite3.Row
        updated = 0
        missing = 0
        invalid = 0
        try:
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

        return {
            "requested": len(normalized),
            "updated": updated,
            "missing": missing,
            "invalid": invalid,
        }
