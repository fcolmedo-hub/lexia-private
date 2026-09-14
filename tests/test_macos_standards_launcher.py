import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LAUNCHER = ROOT / "app" / "ui2" / "macos_desktop.py"


def _load_launcher():
    spec = importlib.util.spec_from_file_location("lexia_macos_desktop_test", LAUNCHER)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


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


def test_macos_launcher_injects_feature_parity_before_shared_runtime():
    source = LAUNCHER.read_text(encoding="utf-8")

    assert 'here / "assets" / "macos_desktop_parity.js"' in source
    assert "hashlib.sha256(desktop_parity.read_bytes())" in source
    assert "runtime_match.start()" in source
    assert "parity_tag" in source


def test_macos_parity_loads_stable_desktop_features_without_continuous_work():
    parity = (
        ROOT / "app" / "ui2" / "assets" / "macos_desktop_parity.js"
    ).read_text(encoding="utf-8")

    assert "window.__lexiaWindowsCaseEvidenceSelectionV2 = true" in parity
    assert "windows_research_manual_sources.js?v=research-manual-sources-1" in parity
    assert "windows_research_manual_sources_merge.js?v=manual-sources-merge-6" in parity
    assert "windows_case_research_bridge.js?v=case-research-7" in parity
    assert "windows_case_research_return.js?v=case-return-3" in parity
    assert "windows_case_nav_state_fix.js?v=case-nav-2" in parity
    assert "windows_research_transport_resilience.js?v=research-resilience-1" in parity
    assert "windows_responsive_layout_guard.js?v=responsive-routes-1" in parity
    assert "windows_maintenance_duplicates.js?v=maintenance-duplicates-2" in parity
    assert "MutationObserver" not in parity
    assert "setInterval(" not in parity


def test_macos_parity_is_injected_before_case_runtime(tmp_path):
    launcher = _load_launcher()
    ui = tmp_path / "app" / "ui2"
    assets = ui / "assets"
    assets.mkdir(parents=True)
    (ui / "index.html").write_text(
        '<html><body><script src="assets/app_runtime.js?v=old"></script></body></html>',
        encoding="utf-8",
    )
    for name in (
        "jurisprudence_search.js",
        "app_runtime.js",
        "macos_desktop_parity.js",
    ):
        (assets / name).write_text("// " + name, encoding="utf-8")

    original = launcher.ensure_ui_assets(tmp_path)
    rendered = (ui / "index.html").read_text(encoding="utf-8")

    assert original is not None
    assert rendered.index("assets/macos_desktop_parity.js") < rendered.index(
        "assets/app_runtime.js"
    )
