from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path


JURISPRUDENCE_ROOT = "Jurisprudencia"


@dataclass(frozen=True)
class JurisprudencePathMetadata:
    jurisdiction: str = ""
    court_type: str = ""
    court_city: str = ""
    chamber: str = ""
    folder_path: str = ""


def _clean(value: str) -> str:
    return " ".join(str(value or "").strip().split())


def metadata_from_path(document_path: str | Path) -> JurisprudencePathMetadata | None:
    """Derive reliable structural metadata from the Jurisprudencia folder tree.

    No court or jurisdiction is inferred from the judgment text here.  The
    physical folder tree remains the source of truth for structural metadata.
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
        return JurisprudencePathMetadata(folder_path="")

    jurisdiction = folders[0] if len(folders) >= 1 else ""
    court_type = folders[1] if len(folders) >= 2 else ""

    # Remaining levels are preserved.  For the current LexIA tree the first
    # extra level normally represents city/seat and the next one chamber/sala.
    # We deliberately do not guess when the tree does not provide them.
    court_city = folders[2] if len(folders) >= 3 else ""
    chamber = folders[3] if len(folders) >= 4 else ""

    return JurisprudencePathMetadata(
        jurisdiction=jurisdiction,
        court_type=court_type,
        court_city=court_city,
        chamber=chamber,
        folder_path="/".join(folders),
    )


def ensure_jurisprudence_index(connection: sqlite3.Connection) -> None:
    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS jurisprudence_index (
            document_path TEXT PRIMARY KEY,
            jurisdiction TEXT NOT NULL DEFAULT '',
            court_type TEXT NOT NULL DEFAULT '',
            court_city TEXT NOT NULL DEFAULT '',
            chamber TEXT NOT NULL DEFAULT '',
            folder_path TEXT NOT NULL DEFAULT '',
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

        CREATE INDEX IF NOT EXISTS idx_jurisprudence_index_jurisdiction
            ON jurisprudence_index(jurisdiction COLLATE NOCASE);

        CREATE INDEX IF NOT EXISTS idx_jurisprudence_index_court
            ON jurisprudence_index(
                jurisdiction COLLATE NOCASE,
                court_type COLLATE NOCASE,
                court_city COLLATE NOCASE,
                chamber COLLATE NOCASE
            );
        """
    )


def rebuild_structural_index(database_path: str | Path) -> dict[str, int]:
    """Populate/update structural jurisprudence metadata for active documents."""
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
                "jurisdiction": 1.0 if metadata.jurisdiction else 0.0,
                "court_type": 1.0 if metadata.court_type else 0.0,
                "court_city": 1.0 if metadata.court_city else 0.0,
                "chamber": 1.0 if metadata.chamber else 0.0,
            }

            connection.execute(
                """
                INSERT INTO jurisprudence_index (
                    document_path,
                    jurisdiction,
                    court_type,
                    court_city,
                    chamber,
                    folder_path,
                    metadata_source,
                    confidence_json,
                    updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, 'path', ?, CURRENT_TIMESTAMP)
                ON CONFLICT(document_path) DO UPDATE SET
                    jurisdiction = excluded.jurisdiction,
                    court_type = excluded.court_type,
                    court_city = excluded.court_city,
                    chamber = excluded.chamber,
                    folder_path = excluded.folder_path,
                    metadata_source = 'path',
                    confidence_json = excluded.confidence_json,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (
                    document_path,
                    metadata.jurisdiction,
                    metadata.court_type,
                    metadata.court_city,
                    metadata.chamber,
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
