from pathlib import Path
from types import SimpleNamespace

from services import ui2_delete_bridge as bridge
from services.ocr_queue_service import OCRQueueService
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
    assert "position:fixed!important" in css
    assert "inset:0 0 0 var(--global-side)!important" in css
    assert ".maint-wrap{width:100%!important;max-width:none!important;margin:0!important" in css
    assert ".maint-history-card{grid-column:2;grid-row:2;max-height:" in css
    assert ".maint-monitor-card{padding:0;overflow:hidden" in css
    assert ".global-sidebar .profile{bottom:178px!important}" in css
    assert "document.getElementById('globalTopbar')?.remove()" in javascript
    assert "Página actual" in javascript
    assert "Páginas completadas" in javascript


def test_home_system_card_and_research_layout_are_corrected():
    root = Path(__file__).parents[1]
    css = (root / "app/ui2/assets/maintenance.css").read_text(encoding="utf-8")
    javascript = (root / "app/ui2/assets/maintenance.js").read_text(encoding="utf-8")

    assert "homeSystemCard.dataset.homeTarget='maintenance'" in javascript
    assert "<i>⚙</i><b>Sistema</b>" in javascript
    assert "window.lexiaMaintenanceOpen?.()" in javascript
    assert "#contextpage .context-layout>.head h1{font-size:25px!important" in css
    assert ".research-main-column>.context-form{flex:0 0 auto!important" in css


class _LiveOCRQueue(_OCRQueue):
    def state(self):
        return {
            **super().state(),
            "document_name": "fallo-en-vivo.pdf",
            "current_page": 7,
            "completed_pages": 6,
            "total_pages": 12,
        }


def test_live_ocr_page_progress_takes_priority_over_persisted_fallback():
    application = SimpleNamespace(ocr_queue=_LiveOCRQueue())

    status = bridge._maintenance_ocr_status(application)

    assert status["document_name"] == "fallo-en-vivo.pdf"
    assert status["current_page"] == 7
    assert status["completed_pages"] == 6
    assert status["total_pages"] == 12
    assert status["page_percentage"] == 50


def test_ocr_service_propagates_the_worker_page_callback():
    root = Path(__file__).parents[1]
    service = (root / "services/ocr_queue_service.py").read_text(encoding="utf-8")
    pipeline = (root / "core/pipeline.py").read_text(encoding="utf-8")

    assert "def _publish_page_progress(" in service
    assert "ocr_progress_callback=self._publish_page_progress" in service
    assert "ocr_progress_callback(page, total)" in pipeline


def test_ocr_service_publishes_the_page_being_scanned():
    service = OCRQueueService.__new__(OCRQueueService)
    service._state = {}

    service._publish_page_progress(0, 12)
    assert service.state()["current_page"] == 1

    service._publish_page_progress(6, 12)
    assert service.state()["current_page"] == 7
    assert service.state()["completed_pages"] == 6
    assert service.state()["total_pages"] == 12

    service._publish_page_progress(12, 12)
    assert service.state()["current_page"] == 12
