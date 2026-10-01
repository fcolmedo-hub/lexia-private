import ast
from pathlib import Path
import sqlite3
import stat
from types import SimpleNamespace

import pytest

from services import file_creation_dates as dates


ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(autouse=True)
def empty_cache():
    dates._cache.clear()
    yield
    dates._cache.clear()


@pytest.mark.parametrize("system,python_version,info,expected", [
    ("darwin", (3, 11), dict(st_birthtime=1700000000, st_ctime=1900000000), 1700000000),
    ("win32", (3, 12), dict(st_birthtime=1700000000, st_ctime=1900000000), 1700000000),
    ("win32", (3, 11), dict(st_ctime=1700000000), 1700000000),
    ("linux", (3, 12), dict(st_ctime=1900000000, st_mtime=1800000000), None),
    ("win32", (3, 12), dict(st_ctime=1900000000), None),
])
def test_true_creation_time_by_platform(monkeypatch, system, python_version, info, expected):
    monkeypatch.setattr(dates, "sys", SimpleNamespace(platform=system, version_info=python_version))
    monkeypatch.setattr(dates.Path, "stat", lambda _self: SimpleNamespace(st_mode=stat.S_IFREG, **info))
    assert dates.file_creation_timestamp("test.pdf") == expected


def test_missing_file_does_not_break_navigation(tmp_path):
    assert dates.file_creation_timestamp(str(tmp_path / "missing.pdf")) is None
    assert dates.file_creation_iso(None) == ""


def test_cache_is_lazy_bounded_and_refreshes(monkeypatch):
    clock = [10]
    stamp = [1700000000]
    calls = []
    monkeypatch.setattr(dates, "monotonic", lambda: clock[0])
    monkeypatch.setattr(dates, "_CACHE_LIMIT", 2)
    def get_stat(path):
        calls.append(str(path))
        return SimpleNamespace(st_mode=stat.S_IFREG, st_birthtime=stamp[0])
    monkeypatch.setattr(dates.Path, "stat", get_stat)
    assert calls == []
    assert dates.file_creation_timestamp("a.pdf") == stamp[0]
    assert dates.file_creation_timestamp("a.pdf") == stamp[0]
    assert calls == ["a.pdf"]
    stamp[0] += 3600
    clock[0] += 61
    assert dates.file_creation_timestamp("a.pdf") == stamp[0]
    dates.file_creation_timestamp("b.pdf")
    dates.file_creation_timestamp("c.pdf")
    assert len(dates._cache) == 2
    assert "a.pdf" not in dates._cache


def browse_function(database):
    # Exercise the real SQL handler without starting its UI server/services.
    tree = ast.parse((ROOT / "app/ui2/server.py").read_text())
    function = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "_navigator_browse_documents")
    namespace = {
        "sqlite3": sqlite3,
        "_filter_catalog_path": lambda: database,
        "_validated_navigator_selections": lambda **kwargs: kwargs.get("selections") or [],
        "_filter_like_pattern": lambda folder: folder.replace("!", "!!").replace("%", "!%").replace("_", "!_") + "/%",
        "_filter_path_shape": lambda path: ("", path.replace("\\", "/").split("/")),
    }
    exec(compile(ast.Module(body=[function], type_ignores=[]), "navigator-handler", "exec"), namespace)
    return namespace["_navigator_browse_documents"]


def setup_catalog(tmp_path, count=205):
    database = tmp_path / "catalog.sqlite3"
    with sqlite3.connect(database) as connection:
        connection.execute("CREATE TABLE documents (path TEXT PRIMARY KEY, name TEXT, category TEXT, extension TEXT, size INTEGER, total_pages INTEGER, updated_at TEXT, is_deleted INTEGER)")
        connection.executemany("INSERT INTO documents VALUES (?,?,'Escritos','.pdf',1,6,?,0)", [
            (f"/library/folder/file-{index:03}.pdf", f"File {index:03}", f"2026-01-{28-index%28:02} 12:00:00")
            for index in range(count)
        ])
        connection.execute("INSERT INTO documents VALUES ('/library/folder/missing.pdf','Missing','Escritos','.pdf',1,6,'2099-01-01',0)")
        connection.execute("INSERT INTO documents VALUES ('/library/folder/deleted.pdf','Deleted','Escritos','.pdf',1,6,'2099-01-01',1)")
    return database


def test_creation_sort_precedes_pagination_and_ignores_reindexing(monkeypatch, tmp_path):
    database = setup_catalog(tmp_path)
    stamps = {f"/library/folder/file-{index:03}.pdf": 1700000000 + index * 3600 for index in range(205)}
    monkeypatch.setattr(dates, "file_creation_timestamp", lambda path: stamps.get(path))
    browse = browse_function(database)
    recent = browse(sort="date_desc", limit=200)
    remaining = browse(sort="date_desc", offset=200)
    assert recent["total"] == 206
    assert recent["items"][0]["document_name"] == "File 204"
    assert len(recent["items"]) == 200
    assert recent["has_more"]
    assert remaining["items"][-1]["document_name"] == "Missing"
    assert remaining["items"][-1]["file_created_at"] == ""
    names = [item["document_name"] for item in recent["items"] + remaining["items"]]
    assert len(names) == len(set(names)) == 206
    oldest = browse(sort="date_asc", limit=2)
    assert [item["document_name"] for item in oldest["items"]] == ["File 000", "File 001"]
    with sqlite3.connect(database) as connection:
        connection.execute("UPDATE documents SET updated_at='2099-12-31' WHERE name='File 000'")
    assert browse(sort="date_desc", limit=1)["items"][0]["document_name"] == "File 204"


def test_name_navigation_stats_only_visible_files_and_keeps_filters(monkeypatch, tmp_path):
    database = setup_catalog(tmp_path)
    calls = []
    monkeypatch.setattr(dates, "file_creation_timestamp", lambda path: calls.append(path) or 1700000000)
    browse = browse_function(database)
    result = browse(sort="name_asc", offset=50, limit=3)
    assert len(calls) == len(result["items"]) == 3
    assert result["items"][0]["document_name"] == "File 050"
    selected = browse(query="204", selections=[{"category": "Escritos", "folder": "/library/folder"}])
    assert selected["total"] == 1
    assert selected["items"][0]["document_name"] == "File 204"
