import hashlib
from pathlib import Path

from app.ui2.macos_desktop import ensure_ui_assets, restore_ui_assets


def test_standards_assets_replace_stale_versions_with_content_hash(tmp_path: Path):
    ui = tmp_path / "app" / "ui2"
    assets = ui / "assets"
    assets.mkdir(parents=True)
    jurisprudence = assets / "jurisprudence_search.js"
    bridge = assets / "search_investigation_bridge.js"
    navigator = ui / "navigator_3_3_4a.js"
    jurisprudence.write_text("window.currentSearch=true;", encoding="utf-8")
    bridge.write_text("window.currentInvestigation=true;", encoding="utf-8")
    navigator.write_text("window.currentNavigator=true;", encoding="utf-8")
    (assets / "app_runtime.js").write_text("", encoding="utf-8")
    standards_ui = assets / "standards_ui.js"
    standards_nav = assets / "standards_nav_fix.js"
    standards_ui.write_text("window.currentStandardsUi=true;", encoding="utf-8")
    standards_nav.write_text("window.currentStandardsNav=true;", encoding="utf-8")
    stale = (
        '<html><body><script>window.LEXIA_STANDARDS_PORT="8515";</script>'
        '<script src="navigator_3_3_4a.js?v=navigator-old"></script>'
        '<script src="assets/jurisprudence_search.js?v=jurisprudence-old"></script>'
        '<script id="lexiaSearchInvestigationBridge" src="assets/search_investigation_bridge.js?v=bridge-old"></script>'
        '<script src="assets/standards_ui.js?v=standards-ui-old"></script>'
        '<script src="assets/standards_nav_fix.js?v=standards-nav-fix-old"></script>'
        '</body></html>'
    )
    index = ui / "index.html"
    index.write_text(stale, encoding="utf-8")

    original = ensure_ui_assets(tmp_path)
    patched = index.read_text(encoding="utf-8")
    ui_hash = hashlib.sha256(standards_ui.read_bytes()).hexdigest()[:12]
    nav_hash = hashlib.sha256(standards_nav.read_bytes()).hexdigest()[:12]
    navigator_hash = hashlib.sha256(navigator.read_bytes()).hexdigest()[:12]
    bridge_hash = hashlib.sha256(bridge.read_bytes()).hexdigest()[:12]
    search_hash = hashlib.sha256(jurisprudence.read_bytes()).hexdigest()[:12]

    assert original == stale
    assert f"standards_ui.js?v=standards-ui-{ui_hash}" in patched
    assert f"standards_nav_fix.js?v=standards-nav-fix-{nav_hash}" in patched
    assert "standards-ui-old" not in patched
    assert "standards-nav-fix-old" not in patched
    assert f"navigator_3_3_4a.js?v=navigator-{navigator_hash}" in patched
    assert f"jurisprudence_search.js?v=jurisprudence-search-{search_hash}" in patched
    assert "bridge-old" not in patched
    bridge_tag = (
        '<script id="lexiaSearchInvestigationBridge" '
        f'src="assets/search_investigation_bridge.js?v=search-investigation-{bridge_hash}"></script>'
    )
    assert bridge_tag in patched
    assert patched.index(bridge_tag) < patched.index("assets/jurisprudence_search.js")

    restore_ui_assets(tmp_path, original)
    assert index.read_text(encoding="utf-8") == stale
