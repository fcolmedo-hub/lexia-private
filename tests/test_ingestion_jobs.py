from pathlib import Path

from storage.ingestion_job_repository import (
    IngestionJobRepository,
)


def test_job_lifecycle(tmp_path: Path) -> None:
    repository = IngestionJobRepository(
        tmp_path / "jobs.sqlite3"
    )

    job_id = repository.create(10)
    repository.checkpoint(
        job_id,
        5,
        "documento.pdf",
        {"new": 5},
    )
    repository.finish(
        job_id,
        "completed",
        {"new": 10},
    )

    latest = repository.latest()

    assert latest is not None
    assert latest["status"] == "completed"
    assert latest["stats"]["new"] == 10
