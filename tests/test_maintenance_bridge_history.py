from types import SimpleNamespace

from services.ui2_delete_bridge import (
    _maintenance_action,
    _maintenance_snapshot,
)


class _History:
    def __init__(self):
        self.calls = []

    def record(self, **payload):
        self.calls.append(payload)

    def recent(self, limit=12):
        return [{"action": "backup", "message": "Copia creada."}]


class _AutoSync:
    def configuration(self):
        return {"mode": "automatic", "schedule_time": "03:00"}

    def state(self):
        return {"phase": "idle", "status": "Listo"}

    def sync_now(self):
        return {"status": "La sincronización fue puesta en cola."}


class _OCRQueue:
    def state(self):
        return {"running": False}

    def stats(self):
        return {"pending": 0, "processing": 0, "error": 0}


class _Activity:
    documents_total = 4
    recent_errors = []

    def snapshot(self, **_kwargs):
        return self


class _Backups:
    def list_backups(self):
        return []


def _application():
    return SimpleNamespace(
        autosync=_AutoSync(),
        ocr_queue=_OCRQueue(),
        activity_center=_Activity(),
        backups=_Backups(),
        maintenance_history=_History(),
    )


def test_manual_sync_is_recorded_in_maintenance_history():
    application = _application()

    result = _maintenance_action(
        application, {"action": "autosync-scan"}
    )

    assert result["ok"] is True
    assert application.maintenance_history.calls == [{
        "action": "autosync-scan",
        "status": "ok",
        "message": "La sincronización fue puesta en cola.",
        "details": {},
    }]


def test_snapshot_includes_persisted_maintenance_history():
    snapshot = _maintenance_snapshot(_application())

    assert snapshot["history"] == [
        {"action": "backup", "message": "Copia creada."}
    ]
