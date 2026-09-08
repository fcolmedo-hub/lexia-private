from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_windows_onedir_build_requires_standards_components():
    source = (ROOT / "scripts" / "rebuild_lexia_app_windows.ps1").read_text(
        encoding="utf-8"
    )
    assert "app\\ui2\\standards_api.py" in source
    assert "app\\ui2\\assets\\standards_ui.js" in source
    assert "app\\ui2\\assets\\standards_nav_fix.js" in source
    assert "services\\standards_service.py" in source


def test_windows_desktop_owns_standards_lifecycle():
    source = (ROOT / "app" / "ui2" / "windows_desktop.py").read_text(
        encoding="utf-8"
    )
    assert "standards_api = start_standards_api" in source
    assert "stop_process(standards_api)" in source
    assert '"LEXIA_STANDARDS_PORT"' in source
