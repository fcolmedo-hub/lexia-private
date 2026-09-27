"""The UI selection must stay local until the user explicitly sends it."""

import json

from services import standards_batch_ui as batch


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
