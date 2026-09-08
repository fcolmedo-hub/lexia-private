import hashlib
from pathlib import Path

from app.ui2.macos_desktop import ensure_ui_assets, restore_ui_assets


def test_standards_assets_replace_stale_versions_with_content_hash(tmp_path: Path):
    ui = tmp_path / "app" / "ui2"
    assets = ui / "assets"
    assets.mkdir(parents=True)
    (assets / "jurisprudence_search.js").write_text("", encoding="utf-8")
    (assets / "app_runtime.js").write_text("", encoding="utf-8")
    standards_ui = assets / "standards_ui.js"
    standards_nav = assets / "standards_nav_fix.js"
    standards_ui.write_text("window.currentStandardsUi=true;", encoding="utf-8")
    standards_nav.write_text("window.currentStandardsNav=true;", encoding="utf-8")
    stale = (
        '<html><body><script>window.LEXIA_STANDARDS_PORT="8515";</script>'
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

    assert original == stale
    assert f"standards_ui.js?v=standards-ui-{ui_hash}" in patched
    assert f"standards_nav_fix.js?v=standards-nav-fix-{nav_hash}" in patched
    assert "standards-ui-old" not in patched
    assert "standards-nav-fix-old" not in patched

    restore_ui_assets(tmp_path, original)
    assert index.read_text(encoding="utf-8") == stale
