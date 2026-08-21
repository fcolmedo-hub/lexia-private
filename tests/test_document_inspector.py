import sqlite3
from pathlib import Path

from services.document_inspector import DocumentInspector


def create_catalog(path: Path) -> None:
    connection = sqlite3.connect(path)
    connection.executescript(
        """
        CREATE TABLE documents (
            path TEXT PRIMARY KEY,
            name TEXT,
            category TEXT,
            extension TEXT,
            size INTEGER,
            content_hash TEXT,
            vector_indexed_hash TEXT,
            text_content TEXT,
            extraction_method TEXT,
            extraction_error TEXT,
            ocr_pages INTEGER,
            total_pages INTEGER,
            duplicate_of TEXT,
            is_deleted INTEGER,
            updated_at TEXT,
            metadata_json TEXT
        );

        CREATE TABLE fragments (
            document_path TEXT,
            fragment_index INTEGER
        );
        """
    )
    connection.execute(
        """
        INSERT INTO documents VALUES (
            ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
        )
        """,
        (
            str((path.parent / "fallo.pdf").resolve()),
            "fallo.pdf",
            "Jurisprudencia",
            ".pdf",
            1000,
            "abc",
            "abc",
            "texto jurídico",
            "native_pdf",
            None,
            0,
            2,
            None,
            0,
            "2026-08-02 10:00:00",
            "{}",
        ),
    )
    connection.execute(
        "INSERT INTO fragments VALUES (?, ?)",
        (
            str((path.parent / "fallo.pdf").resolve()),
            0,
        ),
    )
    connection.commit()
    connection.close()


def test_search_and_inspect(tmp_path: Path):
    catalog = tmp_path / "catalog.sqlite3"
    create_catalog(catalog)

    inspector = DocumentInspector(
        vector_store=None,
        catalog_path=catalog,
        knowledge_path=tmp_path / "none.sqlite3",
    )

    matches = inspector.search("fallo")
    assert len(matches) == 1

    result = inspector.inspect(
        matches[0]["path"]
    )
    assert result.text_extracted
    assert result.fragment_count == 1
