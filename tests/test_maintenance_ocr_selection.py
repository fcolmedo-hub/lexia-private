import threading
from types import SimpleNamespace

import pytest

from services import ocr_queue_service as queue_module
from services import ui2_delete_bridge as bridge
from storage.ocr_queue_repository import OCRQueueRepository


@pytest.fixture
def queue(tmp_path, monkeypatch):
    library = tmp_path / "library"
    library.mkdir()
    monkeypatch.setattr(queue_module, "SETTINGS", SimpleNamespace(library_path=library))
    service = queue_module.OCRQueueService.__new__(queue_module.OCRQueueService)
    service.repository = OCRQueueRepository(tmp_path / "ocr.sqlite")
    service._lock = threading.RLock()
    service._running = False
    service._state = {"running": False}
    service._cancel_requested = threading.Event()
    service.started_paths = []
    monkeypatch.setattr(queue_module.threading, "Thread", lambda **options: SimpleNamespace(
        start=lambda: service.started_paths.extend(options["args"][0])
    ))
    for name in ("one.pdf", "two.pdf", "three.pdf"):
        path = library / name
        path.write_bytes(b"test PDF placeholder")
        service.repository.enqueue(str(path), name, 5)
    service.repository.mark_error(str(library / "two.pdf"), "OCR failed")
    return service, library


def test_only_explicit_files_start_even_when_all_repository_flags_are_selected(queue):
    service, library = queue
    chosen = str(library / "two.pdf")
    assert len(service.repository.get_selected_paths()) == 3
    payload = bridge._maintenance_action(SimpleNamespace(ocr_queue=service), {
        "action": "ocr-start-selected", "paths": [chosen, chosen],
    })
    assert service.started_paths == [chosen]
    assert payload["selected"] == 1
    assert payload["state"]["running"] is True
    assert service.repository.get(str(library / "one.pdf"))["status"] == "pending"


@pytest.mark.parametrize("invalid", ["missing", "completed", "outside", "directory", "bad_type"])
def test_selection_is_validated_completely_before_starting(queue, tmp_path, invalid):
    service, library = queue
    first = str(library / "one.pdf")
    second = str(library / "two.pdf")
    if invalid == "missing":
        (library / "two.pdf").unlink()
    elif invalid == "completed":
        service.repository.mark_completed(second)
    elif invalid == "outside":
        outside = tmp_path / "outside.pdf"
        outside.write_bytes(b"placeholder")
        second = str(outside)
        service.repository.enqueue(second, "outside.pdf", 1)
    elif invalid == "directory":
        second = str(library)
        service.repository.enqueue(second, "library", 0)
    else:
        second = {"path": second}
    with pytest.raises(ValueError):
        service.start_selected(paths=[first, second])
    assert service.started_paths == []
    assert service._running is False


def test_busy_queue_rejects_new_selection_without_replacing_running_job(queue):
    service, library = queue
    service._running = True
    with pytest.raises(ValueError, match="ocupado"):
        bridge._maintenance_action(SimpleNamespace(ocr_queue=service), {
            "action": "ocr-start-selected", "paths": [str(library / "one.pdf")],
        })
    assert service.started_paths == []


def test_status_pagination_reaches_items_beyond_original_hundred(tmp_path):
    repository = OCRQueueRepository(tmp_path / "ocr.sqlite")
    for number in range(125):
        repository.enqueue(f"pending-{number:03}.pdf", f"pending-{number:03}.pdf", 1)
    repository.enqueue("error.pdf", "error.pdf", 1)
    repository.mark_error("error.pdf", "Unreadable")
    application = SimpleNamespace(ocr_queue=SimpleNamespace(repository=repository))
    errors = bridge._maintenance_action(application, {"action": "ocr-list", "status": "error"})
    assert [item["document_path"] for item in errors["items"]] == ["error.pdf"]
    last = bridge._maintenance_action(application, {"action": "ocr-list", "status": "pending", "offset": 100})
    assert last["total"] == 125
    assert len(last["items"]) == 25
    assert last["items"][-1]["document_path"] == "pending-124.pdf"
    assert repository.list_page("pending", limit=10000)["limit"] == 100
    with pytest.raises(ValueError):
        repository.list_page("invalid")
