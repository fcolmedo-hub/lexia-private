from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_windows_shortcut_keeps_stable_launcher_and_lexia_identity() -> None:
    script = (
        ROOT / "scripts" / "fix_lexia_windows_shortcut.ps1"
    ).read_text(encoding="utf-8")

    assert ".venv\\Scripts\\pythonw.exe" in script
    assert "app\\ui2\\windows_desktop_fast.py" in script
    assert "$AppId = 'LexIA.Desktop'" in script
    assert "SetAppUserModelId" in script
    assert "PKEY_AppUserModel" not in script
    assert "9F4C2855-9F79-4B39-A8D0-E1D42DE1D5F3" in script
    assert "LexIA.ico.b64" in script
    assert "PyInstaller" not in script
