from __future__ import annotations

import importlib.util
import os
import sqlite3
import sys
import types
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
UI2 = ROOT / "app" / "ui2"
if str(UI2) not in sys.path:
    sys.path.insert(0, str(UI2))

from backend import LiveReadOnlyAdapter
from models.document import Document
from storage.catalog import DocumentCatalog


def _load_server():
    spec = importlib.util.spec_from_file_location(
        "lexia_ui2_server_home_test", UI2 / "server.py"
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    runtime_stub = types.ModuleType("search_runtime")
    runtime_stub.SearchRuntime = type("SearchRuntime", (), {})
    previous_cwd = Path.cwd()
    try:
        with patch.dict(sys.modules, {"search_runtime": runtime_stub}):
            spec.loader.exec_module(module)
    finally:
        os.chdir(previous_cwd)
    return module


def test_home_search_counter_prefers_current_ui2_table(tmp_path: Path) -> None:
    database = tmp_path / "search_history.sqlite3"
    with sqlite3.connect(database) as connection:
        connection.execute(
            "CREATE TABLE search_history (id INTEGER PRIMARY KEY, query TEXT, created_at TEXT)"
        )
        connection.executemany(
            "INSERT INTO search_history(query,created_at) VALUES (?,CURRENT_TIMESTAMP)",
            [(f"legacy {index}",) for index in range(5)],
        )
        connection.execute(
            "CREATE TABLE ui2_search_history_v2 ("
            "id INTEGER PRIMARY KEY, mode TEXT, query TEXT, created_at TEXT)"
        )
        connection.executemany(
            "INSERT INTO ui2_search_history_v2(mode,query,created_at) "
            "VALUES ('filename',?,CURRENT_TIMESTAMP)",
            [("demanda",), ("sentencia",)],
        )

    snapshot = LiveReadOnlyAdapter._generic_history(database, 5)

    assert snapshot["count"] == 2
    assert snapshot["today_count"] == 2
    assert [row["query"] for row in snapshot["recent"]] == ["sentencia", "demanda"]


def test_catalog_daily_count_uses_real_creation_date(tmp_path: Path) -> None:
    database = tmp_path / "catalog.sqlite3"
    with sqlite3.connect(database) as connection:
        connection.execute(
            """CREATE TABLE documents (
                path TEXT PRIMARY KEY, name TEXT, category TEXT, updated_at TEXT,
                created_at TEXT, extraction_method TEXT, total_pages INTEGER,
                extraction_error TEXT, ocr_pages INTEGER, is_deleted INTEGER
            )"""
        )
        connection.execute(
            "CREATE TABLE fragments (document_path TEXT, fragment_index INTEGER)"
        )
        connection.execute(
            "INSERT INTO documents VALUES "
            "('old','Anterior','General',CURRENT_TIMESTAMP,NULL,'native',1,NULL,0,0)"
        )
        connection.execute(
            "INSERT INTO documents VALUES "
            "('new','Nuevo','General',CURRENT_TIMESTAMP,CURRENT_TIMESTAMP,'native',1,NULL,0,0)"
        )

    adapter = LiveReadOnlyAdapter.__new__(LiveReadOnlyAdapter)
    adapter.catalog_path = database
    catalog = adapter._catalog()

    assert catalog["documents"] == 2
    assert catalog["added_today"] == 1


def test_catalog_records_creation_once_and_preserves_it_on_update(tmp_path: Path) -> None:
    database = tmp_path / "catalog-save.sqlite3"
    catalog = DocumentCatalog(database)
    path = tmp_path / "fallo.pdf"
    path.write_bytes(b"pdf")
    document = Document(
        name=path.name,
        path=path,
        extension=".pdf",
        size=3,
        modified_ns=1,
        content_hash="hash-1",
        text="contenido",
    )
    catalog.save(document)
    with sqlite3.connect(database) as connection:
        created = connection.execute(
            "SELECT created_at FROM documents WHERE path=?", (str(path.resolve()),)
        ).fetchone()[0]
    assert created

    document.modified_ns = 2
    document.text = "contenido actualizado"
    catalog.save(document)
    with sqlite3.connect(database) as connection:
        after_update = connection.execute(
            "SELECT created_at FROM documents WHERE path=?", (str(path.resolve()),)
        ).fetchone()[0]
    assert after_update == created


def test_research_history_is_persistent_and_restores_fields(
    tmp_path: Path, monkeypatch
) -> None:
    server = _load_server()
    monkeypatch.setattr(server, "RUNTIME_ROOT", tmp_path)
    server._record_ui2_context_query_history(
        {
            "query": "responsabilidad estatal",
            "facts": "clausura municipal",
            "objective": "Analizar procedencia",
            "instruction": "priorizar CSJN",
            "max_sources": 9,
        }
    )

    items = server._research_history_items(12)

    assert items == [
        {
            "researchQuery": "responsabilidad estatal",
            "researchFacts": "clausura municipal",
            "researchObjective": "Analizar procedencia",
            "researchInstruction": "priorizar CSJN",
            "maxSources": 9,
            "createdAt": items[0]["createdAt"],
        }
    ]
    assert items[0]["createdAt"]


def test_frontend_removes_demo_metrics_and_loads_research_history() -> None:
    javascript = (UI2 / "assets" / "jurisprudence_search.js").read_text(
        encoding="utf-8"
    )

    assert "installHomeLiveDataFix" in javascript
    assert "catalog.added_today" in javascript
    assert "Sin registro histórico" in javascript
    assert "installPersistentResearchHistory" in javascript
    assert "fetch('/api/research-history'" in javascript
