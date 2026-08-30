from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "app" / "ui2" / "assets"


def test_search_bridge_is_loaded_by_the_shared_windows_macos_asset():
    loader = (ASSETS / "jurisprudence_search.js").read_text(encoding="utf-8")

    assert "search_investigation_bridge.js?v=ui2-3.4.2" in loader
    assert "ensureSearchInvestigationBridge();" in loader


def test_search_bridge_replaces_or_adds_investigate_and_removes_insight():
    bridge = (ASSETS / "search_investigation_bridge.js").read_text(encoding="utf-8")

    assert "openButton.insertAdjacentElement('afterend',investigateButton(openButton))" in bridge
    assert "openButton.textContent='Investigar'" in bridge
    assert "document.querySelector('#'+SEARCH_PAGE_ID+' .insight')?.remove()" in bridge
    assert "window.lexiaSearch320bResolve" in bridge
    assert "input.value=path" in bridge
    assert "navigate('contextpage')" in bridge
    assert "studyTab.click()" in bridge
    assert "startStudy" not in bridge


def test_content_open_is_green_and_investigate_keeps_the_brand_blue():
    bridge = (ASSETS / "search_investigation_bridge.js").read_text(encoding="utf-8")

    assert "openButton.setAttribute(CONTENT_OPEN_ATTR,'1')" in bridge
    assert "background:#149d55!important" in bridge
    assert "background:#0f8044!important" in bridge
    assert "background:#5146f6!important" in bridge
