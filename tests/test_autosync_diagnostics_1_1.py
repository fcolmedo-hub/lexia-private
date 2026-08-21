from pathlib import Path

def test_autosync_diagnostics_1_1_installed():
    source = Path("services/autosync_service.py").read_text(encoding="utf-8")
    required = [
        '"smart_snapshot"',
        '"snapshot_persistence"',
        '"move_reconciliation"',
        '"finalization"',
        '"unaccounted"',
        "snapshot_files",
        "snapshot_changed",
        "snapshot_deleted",
        "Smart Snapshot finalizado",
    ]
    for marker in required:
        assert marker in source
