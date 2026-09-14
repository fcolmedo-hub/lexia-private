from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
AUTOSYNC = ROOT / "services" / "autosync_service.py"
WINDOWS = ROOT / "app" / "ui2" / "windows_desktop.py"
MACOS = ROOT / "app" / "ui2" / "macos_desktop.py"


def test_windows_launcher_scopes_fast_startup_to_child_services() -> None:
    windows = WINDOWS.read_text(encoding="utf-8")
    macos = MACOS.read_text(encoding="utf-8")

    assert 'services_env["LEXIA_WINDOWS_FAST_STARTUP"] = "1"' in windows
    assert 'services_env["LEXIA_WINDOWS_STARTUP_DOCUMENTS"] = str(expected_documents)' in windows
    assert "env=services_env" in windows
    assert 'env["LEXIA_UI2_LIVE_CACHE_SECONDS"] = "30"' in windows
    assert "LEXIA_WINDOWS_FAST_STARTUP" not in macos
    assert "LEXIA_UI2_LIVE_CACHE_SECONDS" not in macos


def test_autosync_skips_only_windows_smart_reconcile_with_existing_snapshot() -> None:
    source = AUTOSYNC.read_text(encoding="utf-8")

    assert 'os.environ.get("LEXIA_WINDOWS_FAST_STARTUP") == "1"' in source
    assert 'os.environ.get("LEXIA_WINDOWS_STARTUP_DOCUMENTS", "0")' in source
    assert "else self.catalog.stats()[\"documents\"]" in source
    assert "and self.library_snapshot.initialized()" in source
    assert "and not windows_fast_startup" in source
    assert 'self.request_full_scan(\n                "startup_manual_override"' in source
    assert "reconciliacion completa omitida" in source
