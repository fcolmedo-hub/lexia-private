"""The UI selection must stay local until the user explicitly sends it."""

import json
import sqlite3

from services import standards_batch_ui as batch


def test_tree_keeps_full_windows_paths_and_lists_nested_folders(tmp_path, monkeypatch):
    catalog = tmp_path / "catalog.sqlite3"
    with sqlite3.connect(catalog) as connection:
        connection.execute("CREATE TABLE documents(path TEXT, category TEXT, is_deleted INTEGER)")
        connection.executemany("INSERT INTO documents VALUES(?,?,0)", [
            (r"D:\LexIA\data_test\Jurisprudencia\Civil\Cámara A\fallo1.pdf", "Jurisprudencia"),
            (r"D:\LexIA\data_test\Jurisprudencia\Civil\Cámara A\fallo2.pdf", "Jurisprudencia"),
            (r"D:\LexIA\data_test\Jurisprudencia\Laboral\fallo3.pdf", "Jurisprudencia"),
        ])
    monkeypatch.setattr(batch, "CATALOG", catalog)
    batch._TREE_CACHE.clear()

    roots = batch.folder_tree()
    assert len(roots) == 1
    assert roots[0]["path"] == r"D:\LexIA\data_test\Jurisprudencia"
    assert roots[0]["count"] == 3
    branches = batch.folder_tree(roots[0]["path"])
    assert [item["name"] for item in branches] == ["Civil", "Laboral"]
    assert batch.folder_tree(branches[0]["path"])[0]["count"] == 2


def test_court_suggestions_combine_folder_hierarchy_and_catalogued_courts(tmp_path, monkeypatch):
    monkeypatch.setattr(batch, "CATALOG", tmp_path / "catalog.sqlite3")
    monkeypatch.setattr(batch, "DB", tmp_path / "standards.sqlite3")
    with sqlite3.connect(batch.CATALOG) as connection:
        connection.execute("CREATE TABLE documents(path TEXT, category TEXT, is_deleted INTEGER)")
        connection.executemany("INSERT INTO documents VALUES(?,?,0)", [
            (r"D:\LexIA\Jurisprudencia\Santa Fe\Rosario\Civil y Comercial\Primera Instancia\Nominacion\1º\fallo.pdf", "Jurisprudencia"),
            (r"D:\LexIA\Jurisprudencia\Civil\Cámara A\fallo.pdf", "Jurisprudencia"),
            (r"D:\LexIA\Jurisprudencia\Santa Fe\Rosario\Cámara Federal\2025\fallo.pdf", "Jurisprudencia"),
            (r"D:\LexIA\Jurisprudencia\Santa Fe\Contencioso Administrativo\Rosario\2024\fallo.pdf", "Jurisprudencia"),
            (r"D:\LexIA\Jurisprudencia\Santa Fe\Contencioso Administrativo\Santa Fe\2025\fallo.pdf", "Jurisprudencia"),
        ])
    with sqlite3.connect(batch.DB) as connection:
        connection.execute("CREATE TABLE documents(court TEXT)")
        connection.execute("INSERT INTO documents VALUES('CSJN')")
    batch._TREE_CACHE.clear()
    result = batch.court_suggestions()
    court = next(item for item in result["courts"] if item["label"].endswith("Nominación 1º"))
    assert "Santa Fe › Rosario › Civil y Comercial › Primera Instancia" in court["label"]
    assert court["suggested"] == "Juzgado de Primera Instancia en lo Civil y Comercial de 1ª Nominación de Rosario"
    assert "Cámara A" in [item["label"].split(" › ")[-1] for item in result["courts"]]
    assert any(item["label"].endswith("Rosario › Cámara Federal") and
               item["suggested"] == "Cámara Federal de Rosario" for item in result["courts"])
    assert any(item["label"].endswith("Contencioso Administrativo › Rosario") for item in result["courts"])
    assert any(item["label"].endswith("Contencioso Administrativo › Santa Fe") for item in result["courts"])
    assert "Santa Fe" not in [item["label"] for item in result["courts"]]
    assert result["catalogued"] == ["CSJN"]


def test_selection_partitions_large_folder_without_sending_to_api(tmp_path, monkeypatch):
    paths = [str(tmp_path / f"fallo-{number:04}.pdf") for number in range(501)]
    monkeypatch.setattr(batch, "RUNS", tmp_path / "runs")
    monkeypatch.setattr(batch, "preview", lambda folder: {"items": paths})
    monkeypatch.setattr(batch, "_start", lambda job_id, action: json.loads(
        (batch._job_dir(job_id) / "job.json").read_text(encoding="utf-8")))

    job = batch.prepare({"folder": str(tmp_path), "paths": paths, "court": ""})

    assert job["total"] == 501
    assert job["chunks"] == 3
    assert job["steps"] == 11
    assert job["run_ids"] == [None, None, None]
    assert (batch._job_dir(job["job_id"]) / "selection.txt").read_text().splitlines() == paths


def test_manual_court_is_required_and_api_mode_does_not_copy_stale_court(tmp_path, monkeypatch):
    path = str(tmp_path / "fallo.pdf")
    monkeypatch.setattr(batch, "RUNS", tmp_path / "runs")
    monkeypatch.setattr(batch, "preview", lambda folder: {"items": [path]})
    monkeypatch.setattr(batch, "_start", lambda job_id, action: json.loads(
        (batch._job_dir(job_id) / "job.json").read_text(encoding="utf-8")))
    try:
        batch.prepare({"folder": str(tmp_path), "paths": [path], "court_mode": "manual", "court": ""})
    except ValueError as error:
        assert "Indicá el tribunal" in str(error)
    else:
        raise AssertionError("A common court must be named")

    job = batch.prepare({"folder": str(tmp_path), "paths": [path], "court_mode": "api", "court": "CSJN"})
    assert job["court_mode"] == "api"
    assert job["court"] == ""


def test_batch_action_requires_correct_stage_and_resumable_error(tmp_path, monkeypatch):
    monkeypatch.setattr(batch, "RUNS", tmp_path / "runs")
    job = {"job_id": "std-ui-test", "phase": "ready_to_send", "run_ids": ["part-1"],
           "steps": 5, "log": []}
    batch._write(job)
    calls = []
    monkeypatch.setattr(batch, "_start", lambda job_id, action: calls.append(action) or job)

    batch.act("std-ui-test", "send")
    assert calls == ["send"]
    try:
        batch.act("std-ui-test", "relations")
    except ValueError:
        pass
    else:
        raise AssertionError("Relations cannot be sent before their preparation")
