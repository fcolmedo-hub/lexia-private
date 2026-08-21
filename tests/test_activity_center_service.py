import sqlite3
from pathlib import Path

from services.activity_center_service import (
    ActivityCenterService,
)


class AutoSync:
    def state(self):
        return {
            "phase": "indexing",
            "status": "Indexando",
            "current_file": "fallo.pdf",
            "processed": 1,
            "total": 3,
            "percentage": 66,
            "last_error": "",
            "last_sync": "",
        }


class OCRQueue:
    def state(self):
        return {
            "running": False,
            "current_file": "",
            "processed": 0,
            "total": 0,
        }

    def stats(self):
        return {
            "pending": 2,
            "processing": 0,
            "error": 0,
        }

    def list_pending(self):
        return []


def create_catalog(path: Path):
    connection = sqlite3.connect(path)
    connection.execute(
        """
        CREATE TABLE documents (
            name TEXT,
            path TEXT,
            category TEXT,
            extraction_method TEXT,
            total_pages INTEGER,
            updated_at TEXT,
            duplicate_of TEXT,
            extraction_error TEXT,
            is_deleted INTEGER
        )
        """
    )
    connection.execute(
        """
        INSERT INTO documents VALUES (
            'fallo.pdf',
            'fallo.pdf',
            'Jurisprudencia',
            'native_pdf',
            10,
            '2026-08-02 20:00:00',
            NULL,
            NULL,
            0
        )
        """
    )
    connection.commit()
    connection.close()


def test_snapshot(tmp_path: Path):
    catalog = tmp_path / "catalog.sqlite3"
    create_catalog(catalog)

    service = ActivityCenterService(
        AutoSync(),
        OCRQueue(),
        catalog_path=catalog,
    )
    snapshot = service.snapshot()

    assert snapshot.documents_total == 1
    assert snapshot.busy is True
    assert snapshot.ocr_pending == 2
    assert snapshot.recent_documents[0]["name"] == (
        "fallo.pdf"
    )
