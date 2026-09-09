from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_windows_onedir_build_requires_standards_components():
    source = (ROOT / "scripts" / "rebuild_lexia_app_windows.ps1").read_text(
        encoding="utf-8"
    )
    assert "app\\ui2\\standards_api.py" in source
    assert "app\\ui2\\assets\\standards_ui.js" in source
    assert "app\\ui2\\assets\\standards_nav_fix.js" in source
    assert "app\\ui2\\navigator_3_3_4a.js" in source
    assert "app\\ui2\\assets\\jurisprudence_search.js" in source
    assert "app\\ui2\\assets\\search_investigation_bridge.js" in source
    assert "services\\standards_service.py" in source
    assert "services\\standards_canonicalizer.py" in source


def test_windows_build_bundles_and_verifies_cffi_backend():
    source = (ROOT / "scripts" / "rebuild_lexia_app_windows.ps1").read_text(
        encoding="utf-8"
    )
    assert "Test-PythonModule '_cffi_backend'" in source
    assert "'--hidden-import','_cffi_backend'" in source
    assert "'_cffi_backend*.pyd'" in source
    assert "No se reemplazó la instalación actual" in source


def test_windows_desktop_owns_standards_lifecycle():
    source = (ROOT / "app" / "ui2" / "windows_desktop.py").read_text(
        encoding="utf-8"
    )
    assert "standards_api = start_standards_api" in source
    assert "stop_process(standards_api)" in source
    assert '"LEXIA_STANDARDS_PORT"' in source
