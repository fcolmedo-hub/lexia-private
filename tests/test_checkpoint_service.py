from pathlib import Path

from services.checkpoint_service import CheckpointService


def test_checkpoint_lifecycle(tmp_path: Path) -> None:
    service = CheckpointService(tmp_path / "checkpoints")
    state = service.begin(
        task="library_sync",
        phase="scanning",
        total=1000,
    )
    assert state.completed is False
    assert service.pending() is not None

    service.update(
        phase="indexing",
        processed=500,
        total=1000,
        current_file="fallo.pdf",
        force=True,
    )
    current = service.pending()
    assert current is not None
    assert current.phase == "indexing"
    assert current.processed == 500
    assert current.current_file == "fallo.pdf"

    service.complete()
    assert service.pending() is None
    assert list(
        (tmp_path / "checkpoints" / "history").glob("*.json")
    )


def test_checkpoint_survives_new_instance(tmp_path: Path) -> None:
    root = tmp_path / "checkpoints"
    CheckpointService(root).begin(
        task="ocr",
        phase="processing",
        total=25,
    )
    recovered = CheckpointService(root).pending()
    assert recovered is not None
    assert recovered.task == "ocr"
    assert recovered.total == 25


def test_failed_checkpoint_remains_pending(tmp_path: Path) -> None:
    service = CheckpointService(tmp_path / "checkpoints")
    service.begin(
        task="library_sync",
        phase="indexing",
    )
    service.fail("corte inesperado")
    recovered = service.pending()
    assert recovered is not None
    assert recovered.interrupted is True
    assert recovered.error == "corte inesperado"


def test_cancel_removes_current_checkpoint(tmp_path: Path) -> None:
    service = CheckpointService(tmp_path / "checkpoints")
    service.begin(task="ocr", phase="processing")
    service.cancel()
    assert service.pending() is None
