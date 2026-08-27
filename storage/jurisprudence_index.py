from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path


JURISPRUDENCE_ROOT = "Jurisprudencia"


@dataclass(frozen=True)
class JurisprudencePathMetadata:
    # Datos organizativos derivados de la ruta. No equivalen necesariamente
    # al tribunal que dictó la sentencia.
    scope: str = ""
    province: str = ""
    hierarchy_group: str = ""
    hierarchy_location: str = ""
    hierarchy_detail: str = ""
    folder_path: str = ""


def _clean(value: str) -> str:
    return " ".join(str(value or "").strip().split())


def _contains_federal(parts: list[str]) -> bool:
    folded = " / ".join(parts).casefold()
    return "federal" in folded


def metadata_from_path(document_path: str | Path) -> JurisprudencePathMetadata | None:
    """Derive only organizational metadata from the Jurisprudencia tree.

    Important: a folder may group decisions by hierarchical dependence rather
    than by the court that actually issued them.  Therefore the path never
    determines the exact deciding court.  That value must later be extracted
    from the document itself.
    """
    path = Path(document_path)
    parts = list(path.parts)

    try:
        root_index = next(
            i for i, part in enumerate(parts)
            if part.casefold() == JURISPRUDENCE_ROOT.casefold()
        )
    except StopIteration:
        return None

    folders = [_clean(p) for p in parts[root_index + 1 : -1] if _clean(p)]
    if not folders:
        return JurisprudencePathMetadata()

    first = folders[0]
    folded_first = first.casefold()

    scope = ""
    province = ""
    hierarchy_group = ""
    hierarchy_location = ""
    hierarchy_detail = ""

    if folded_first == "csjn":
        scope = "Nacional"
        hierarchy_group = "CSJN"

    elif folded_first == "camaras nacionales":
        scope = "Nacional"
        hierarchy_group = "/".join(folders[:2]) if len(folders) >= 2 else first
        hierarchy_location = folders[2] if len(folders) >= 3 else ""
        hierarchy_detail = "/".join(folders[3:]) if len(folders) >= 4 else ""

    elif folded_first == "otras jurisdicciones":
        # Carpeta puramente organizativa. No se infiere jurisdicción ni tribunal.
        hierarchy_group = first
        hierarchy_detail = "/".join(folders[1:]) if len(folders) >= 2 else ""

    else:
        # En el árbol actual el primer nivel suele ser una provincia o región
        # geográfica. Puede contener tanto justicia provincial como federal.
        province = first

        if _contains_federal(folders[1:]):
            scope = "Federal"
        elif any("camara federal" in part.casefold() for part in folders[1:]):
            scope = "Federal"
        else:
            scope = "Provincial"

        hierarchy_group = folders[1] if len(folders) >= 2 else ""

        # Casos conocidos del árbol actual: se preserva la semántica física
        # sin afirmar que esos niveles describan el tribunal decisor.
        if hierarchy_group.casefold() == "1 instancia":
            # Ej.: Santa Fe/1 Instancia/Federal/Santa Fe/1
            hierarchy_location = folders[3] if len(folders) >= 4 else ""
            hierarchy_detail = "/".join(folders[4:]) if len(folders) >= 5 else ""
        elif hierarchy_group.casefold().startswith("camara federal"):
            # Ej.: Santa Fe/Camara Federal de Rosario
            if "rosario" in hierarchy_group.casefold():
                hierarchy_location = "Rosario"
            hierarchy_detail = "/".join(folders[2:]) if len(folders) >= 3 else ""
        else:
            hierarchy_location = folders[2] if len(folders) >= 3 else ""
            hierarchy_detail = "/".join(folders[3:]) if len(folders) >= 4 else ""

    return JurisprudencePathMetadata(
        scope=scope,
        province=province,
        hierarchy_group=hierarchy_group,
        hierarchy_location=hierarchy_location,
        hierarchy_detail=hierarchy_detail,
        folder_path="/".join(folders),
    )


def _ensure_columns(connection: sqlite3.Connection) -> None:
    existing = {
        str(row[1])
        for row in connection.execute("PRAGMA table_info(jurisprudence_index)").fetchall()
    }
    additions = {
        "scope": "TEXT NOT NULL DEFAULT ''",
        "province": "TEXT NOT NULL DEFAULT ''",
        "hierarchy_group": "TEXT NOT NULL DEFAULT ''",
        "hierarchy_location": "TEXT NOT NULL DEFAULT ''",
        "hierarchy_detail": "TEXT NOT NULL DEFAULT ''",
        "decision_court_name": "TEXT NOT NULL DEFAULT ''",
        "decision_court_source": "TEXT NOT NULL DEFAULT ''",
    }
    for column, definition in additions.items():
        if column not in existing:
            connection.execute(
                f"ALTER TABLE jurisprudence_index ADD COLUMN {column} {definition}"
            )


def ensure_jurisprudence_index(connection: sqlite3.Connection) -> None:
    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS jurisprudence_index (
            document_path TEXT PRIMARY KEY,
            scope TEXT NOT NULL DEFAULT '',
            province TEXT NOT NULL DEFAULT '',
            hierarchy_group TEXT NOT NULL DEFAULT '',
            hierarchy_location TEXT NOT NULL DEFAULT '',
            hierarchy_detail TEXT NOT NULL DEFAULT '',
            folder_path TEXT NOT NULL DEFAULT '',

            decision_court_name TEXT NOT NULL DEFAULT '',
            decision_court_source TEXT NOT NULL DEFAULT '',

            case_title TEXT NOT NULL DEFAULT '',
            case_number TEXT NOT NULL DEFAULT '',
            decision_date TEXT NOT NULL DEFAULT '',
            plaintiff TEXT NOT NULL DEFAULT '',
            defendant TEXT NOT NULL DEFAULT '',
            laws_json TEXT NOT NULL DEFAULT '[]',
            articles_json TEXT NOT NULL DEFAULT '[]',
            legal_topics_json TEXT NOT NULL DEFAULT '[]',
            decision_summary TEXT NOT NULL DEFAULT '',
            metadata_source TEXT NOT NULL DEFAULT 'path',
            confidence_json TEXT NOT NULL DEFAULT '{}',
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (document_path)
                REFERENCES documents(path)
                ON DELETE CASCADE
        );
        """
    )
    _ensure_columns(connection)
    connection.executescript(
        """
        CREATE INDEX IF NOT EXISTS idx_jurisprudence_index_scope
            ON jurisprudence_index(scope COLLATE NOCASE);

        CREATE INDEX IF NOT EXISTS idx_jurisprudence_index_hierarchy
            ON jurisprudence_index(
                scope COLLATE NOCASE,
                province COLLATE NOCASE,
                hierarchy_group COLLATE NOCASE,
                hierarchy_location COLLATE NOCASE
            );
        """
    )


def rebuild_structural_index(database_path: str | Path) -> dict[str, int]:
    """Populate/update organizational jurisprudence metadata."""
    database_path = Path(database_path)
    connection = sqlite3.connect(database_path, timeout=30)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA busy_timeout = 30000")
    connection.execute("PRAGMA foreign_keys = ON")

    stats = {"scanned": 0, "indexed": 0, "removed": 0}

    try:
        ensure_jurisprudence_index(connection)

        rows = connection.execute(
            """
            SELECT path
            FROM documents
            WHERE COALESCE(is_deleted, 0) = 0
              AND category = 'Jurisprudencia'
            ORDER BY path COLLATE NOCASE
            """
        ).fetchall()

        active_paths: set[str] = set()

        for row in rows:
            stats["scanned"] += 1
            document_path = str(row["path"])
            metadata = metadata_from_path(document_path)
            if metadata is None:
                continue

            active_paths.add(document_path)
            confidence = {
                "scope": 1.0 if metadata.scope else 0.0,
                "province": 1.0 if metadata.province else 0.0,
                "hierarchy_group": 1.0 if metadata.hierarchy_group else 0.0,
                "hierarchy_location": 1.0 if metadata.hierarchy_location else 0.0,
                "hierarchy_detail": 1.0 if metadata.hierarchy_detail else 0.0,
                "decision_court_name": 0.0,
            }

            connection.execute(
                """
                INSERT INTO jurisprudence_index (
                    document_path,
                    scope,
                    province,
                    hierarchy_group,
                    hierarchy_location,
                    hierarchy_detail,
                    folder_path,
                    metadata_source,
                    confidence_json,
                    updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, 'path-organizational', ?, CURRENT_TIMESTAMP)
                ON CONFLICT(document_path) DO UPDATE SET
                    scope = excluded.scope,
                    province = excluded.province,
                    hierarchy_group = excluded.hierarchy_group,
                    hierarchy_location = excluded.hierarchy_location,
                    hierarchy_detail = excluded.hierarchy_detail,
                    folder_path = excluded.folder_path,
                    metadata_source = 'path-organizational',
                    confidence_json = excluded.confidence_json,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (
                    document_path,
                    metadata.scope,
                    metadata.province,
                    metadata.hierarchy_group,
                    metadata.hierarchy_location,
                    metadata.hierarchy_detail,
                    metadata.folder_path,
                    json.dumps(confidence, ensure_ascii=False, separators=(",", ":")),
                ),
            )
            stats["indexed"] += 1

        existing = connection.execute(
            "SELECT document_path FROM jurisprudence_index"
        ).fetchall()
        stale = [
            str(row["document_path"])
            for row in existing
            if str(row["document_path"]) not in active_paths
        ]
        if stale:
            connection.executemany(
                "DELETE FROM jurisprudence_index WHERE document_path = ?",
                [(path,) for path in stale],
            )
            stats["removed"] = len(stale)

        connection.commit()
        return stats
    finally:
        connection.close()
