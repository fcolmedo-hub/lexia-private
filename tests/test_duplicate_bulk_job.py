import sqlite3
import time
from pathlib import Path
from types import SimpleNamespace

from services import windows_research_manual_sources as source


def test_bulk_delete_checks_catalog_and_keeps_original(tmp_path, monkeypatch):
    library = tmp_path / "library"
    library.mkdir()
    original = library / "original.pdf"
    duplicates = [library / "copy-1.pdf", library / "copy-2.pdf"]
    for path in [original, *duplicates]:
        path.write_bytes(b"document")
    catalog = tmp_path / "catalog.sqlite3"
    with sqlite3.connect(catalog) as con:
        con.execute("CREATE TABLE documents(path TEXT, name TEXT, category TEXT, size INTEGER, updated_at TEXT, duplicate_of TEXT, is_deleted INTEGER)")
        con.executemany("INSERT INTO documents VALUES(?,?,?,?,?,?,0)", [(str(path), path.name, "Jurisprudencia", 8, "", str(original) if path != original else None) for path in [original, *duplicates]])

    monkeypatch.setattr(source, "SETTINGS", SimpleNamespace(library_path=library, catalog_path=catalog))
    with source._DUPLICATE_JOB_LOCK:
        source._DUPLICATE_JOB.update(running=False, total=0, processed=0, deleted=0, failed=[])

    def delete(path, *, require_duplicate=False):
        assert require_duplicate
        with sqlite3.connect(catalog) as con:
            row = con.execute("SELECT duplicate_of FROM documents WHERE path=? AND is_deleted=0", (str(path),)).fetchone()
            assert row and row[0] == str(original)
            con.execute("UPDATE documents SET is_deleted=1 WHERE path=?", (str(path),))
        Path(path).unlink()

    app = SimpleNamespace(secure_document_deletion=SimpleNamespace(delete=delete))
    try:
        source._start_duplicate_job(app, [str(original)])
    except ValueError:
        pass
    else:
        raise AssertionError("El original no puede ingresar al lote")

    source._start_duplicate_job(app, [str(path) for path in duplicates])
    for _ in range(200):
        result = source._duplicate_job_snapshot()
        if not result["running"]:
            break
        time.sleep(0.01)
    assert result["processed"] == result["deleted"] == 2
    assert result["failed"] == []
    assert original.is_file()
    assert all(not path.exists() for path in duplicates)
