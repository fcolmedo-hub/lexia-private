from pathlib import Path
from time import monotonic, sleep
from types import SimpleNamespace

from services import ui2_delete_bridge as bridge


class _History:
    def __init__(self):
        self.calls = []
        self.limit = None

    def recent(self, limit=12):
        self.limit = limit
        return [{
            "action": "backup",
            "status": "ok",
            "message": "Copia creada.",
            "created_at": "2026-08-22T10:00:00",
        }]

    def record(self, **payload):
        self.calls.append(payload)


class _AutoSync:
    def state(self):
        return {
            "phase": "idle",
            "status": "Biblioteca al día",
            "processed": 0,
            "total": 0,
            "percentage": 0,
        }

    def configuration(self):
        return {"mode": "automatic", "schedule_time": "03:00"}


class _OCRRepository:
    def get_selected_paths(self):
        return ["uno.pdf", "dos.pdf", "tres.pdf"]


class _OCR:
    def __init__(self):
        self.repository = _OCRRepository()
        self.selected = False

    def state(self):
        return {
            "running": False,
            "stage": "idle",
            "processed": 0,
            "total": 0,
        }

    def stats(self):
        return {"pending": 3, "processing": 0, "error": 0}

    def select_all(self, selected):
        self.selected = selected

    def start_selected(self):
        return True


class _Activity:
    documents_total = 86_768
    recent_errors = []

    def snapshot(self, **options):
        assert options == {"recent_limit": 0, "error_limit": 8}
        return self


class _Backups:
    def list_backups(self):
        return []


class _Platform:
    def status(self):
        return {
            "product": "LexIA Platform",
            "version": "2.1.0-dev",
            "build": "2026.08.03.2101",
            "channel": "DEV",
            "healthy": True,
            "components": {},
            "settings": {},
        }


class _Health:
    def report(self):
        return {"healthy": True, "version": "2.1.0-dev"}


def _application():
    return SimpleNamespace(
        autosync=_AutoSync(),
        ocr_queue=_OCR(),
        activity_center=_Activity(),
        backups=_Backups(),
        maintenance_history=_History(),
        platform_info=_Platform(),
        health=_Health(),
    )


def test_snapshot_is_bounded_and_exposes_monitor_and_about():
    application = _application()

    snapshot = bridge._maintenance_snapshot(application)

    assert application.maintenance_history.limit == 8
    assert snapshot["history"][0]["action"] == "backup"
    assert snapshot["platform"]["version"] == "2.1.0-dev"
    assert snapshot["operation"]["function"] == "idle"
    assert len(snapshot["monitor"]) >= 2


def test_ocr_action_reports_selected_documents_and_is_recorded():
    application = _application()

    result = bridge._maintenance_action(
        application,
        {"action": "ocr-start-all"},
    )

    assert result["started"] is True
    assert result["selected"] == 3
    assert application.ocr_queue.selected is True
    assert application.maintenance_history.calls[-1]["details"] == {
        "started": True,
        "selected": 3,
    }


def test_diagnostic_runs_in_background():
    application = _application()

    result = bridge._maintenance_action(
        application,
        {"action": "diagnostic"},
    )

    assert result["started"] is True
    deadline = monotonic() + 1
    while monotonic() < deadline:
        with bridge._MAINTENANCE_DIAGNOSTIC_LOCK:
            state = dict(bridge._MAINTENANCE_DIAGNOSTIC)
        if not state["running"]:
            break
        sleep(0.01)
    assert state["running"] is False
    assert state["report"]["healthy"] is True


def test_ui_has_live_monitor_navigation_and_persistent_feedback():
    source = (
        Path(__file__).parents[1]
        / "app"
        / "ui2"
        / "assets"
        / "maintenance.js"
    ).read_text(encoding="utf-8")

    assert "slice(0,8)" in source
    assert "Monitor técnico" in source
    assert "Acerca de LexIA" in source
    assert "data-maint-target" in source
    assert "keepPollingUntil" in source
    assert "Estado actualizado a las" in source
