from pathlib import Path
from types import SimpleNamespace

from services import ui2_delete_bridge as bridge
from storage.ocr_queue_repository import OCRQueueRepository


class _Repository:
    def get(self, document_path):
        assert document_path == r"D:\Biblioteca\fallo.pdf"
        return {
            "document_name": "fallo.pdf",
            "total_pages": 10,
            "progress_page": 4,
        }


class _OCRQueue:
    repository = _Repository()

    def state(self):
        return {
            "running": True,
            "current_file": r"D:\Biblioteca\fallo.pdf",
            "processed": 1,
            "total": 3,
            "stage": "ocr",
            "stopping": False,
            "error": "",
        }

    def stats(self):
        return {"pending": 2, "processing": 1, "completed": 0, "error": 0}


def test_ocr_projection_exposes_document_and_page_progress():
    application = SimpleNamespace(ocr_queue=_OCRQueue())

    status = bridge._maintenance_ocr_status(application)

    assert status["document_name"] == "fallo.pdf"
    assert status["document_position"] == 2
    assert status["current_page"] == 5
    assert status["completed_pages"] == 4
    assert status["total_pages"] == 10
    assert status["page_percentage"] == 40


def test_repository_reads_one_ocr_item(tmp_path):
    repository = OCRQueueRepository(tmp_path / "ocr.sqlite3")
    repository.enqueue("fallo.pdf", "fallo.pdf", 12)
    repository.mark_processing("fallo.pdf")
    repository.update_progress("fallo.pdf", 7)

    item = repository.get("fallo.pdf")

    assert item["document_name"] == "fallo.pdf"
    assert item["total_pages"] == 12
    assert item["progress_page"] == 7


def test_maintenance_layout_is_bounded_and_topbar_is_removed():
    root = Path(__file__).parents[1]
    css = (root / "app/ui2/assets/maintenance.css").read_text(encoding="utf-8")
    javascript = (root / "app/ui2/assets/maintenance.js").read_text(encoding="utf-8")

    assert "#globalTopbar,.global-topbar{display:none!important}" in css
    assert "height:100dvh!important" in css
    assert ".maint-history-card{grid-column:1/-1;max-height:" in css
    assert ".maint-monitor-card{padding:0;overflow:hidden" in css
    assert ".global-sidebar .profile{bottom:178px!important}" in css
    assert "document.getElementById('globalTopbar')?.remove()" in javascript
    assert "Página actual" in javascript
    assert "Páginas completadas" in javascript
