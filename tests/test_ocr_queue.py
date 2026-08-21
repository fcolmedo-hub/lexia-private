from pathlib import Path

from storage.ocr_queue_repository import (
    OCRQueueRepository,
)


def test_select_individual_and_all(tmp_path: Path):
    repo = OCRQueueRepository(
        tmp_path / "ocr.sqlite3"
    )
    repo.enqueue("a.pdf", "a.pdf", 10)
    repo.enqueue("b.pdf", "b.pdf", 20)

    repo.set_selected("a.pdf", False)
    assert repo.get_selected_paths() == ["b.pdf"]

    repo.select_all(True)
    assert set(repo.get_selected_paths()) == {
        "a.pdf",
        "b.pdf",
    }


def test_completed_leaves_pending_list(tmp_path: Path):
    repo = OCRQueueRepository(
        tmp_path / "ocr.sqlite3"
    )
    repo.enqueue("a.pdf", "a.pdf", 10)
    repo.mark_completed("a.pdf")
    assert repo.list_pending() == []
