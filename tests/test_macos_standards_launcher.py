from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LAUNCHER = ROOT / "app" / "ui2" / "macos_desktop.py"


def test_macos_launcher_starts_and_stops_standards_api():
    source = LAUNCHER.read_text(encoding="utf-8")

    assert 'STANDARDS_PORT = int(os.environ.get("LEXIA_STANDARDS_PORT", "8515"))' in source
    assert 'root / "app" / "ui2" / "standards_api.py"' in source
    assert 'env["LEXIA_STANDARDS_PORT"] = str(STANDARDS_PORT)' in source
    assert "standards_api = subprocess.Popen(" in source
    assert "if not wait_tcp(STANDARDS_PORT, 20):" in source
    assert "stop_process(standards_api)" in source


def test_macos_launcher_can_inject_standards_assets():
    source = LAUNCHER.read_text(encoding="utf-8")

    assert 'here / "assets" / "standards_ui.js"' in source
    assert 'here / "assets" / "standards_nav_fix.js"' in source
    assert "window.LEXIA_STANDARDS_PORT" in source
    assert "hashlib.sha256(standards_ui.read_bytes())" in source
    assert "hashlib.sha256(standards_nav_fix.read_bytes())" in source
    assert "assets/standards_ui\\.js" in source
    assert "assets/standards_nav_fix\\.js" in source
