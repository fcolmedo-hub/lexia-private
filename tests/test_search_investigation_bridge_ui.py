from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "app" / "ui2" / "assets"


def test_search_bridge_is_loaded_by_the_shared_windows_macos_asset():
    loader = (ASSETS / "jurisprudence_search.js").read_text(encoding="utf-8")

    assert "search_investigation_bridge.js?v=ui2-3.4.5-single-menu" in loader
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
    load_study = bridge[bridge.index("function loadStudyFile"):bridge.index("function installHtmlViewerFix")]
    assert "startStudy" not in load_study


def test_content_open_is_green_and_investigate_keeps_the_brand_blue():
    bridge = (ASSETS / "search_investigation_bridge.js").read_text(encoding="utf-8")

    assert "openButton.setAttribute(CONTENT_OPEN_ATTR,'1')" in bridge
    assert "button.removeAttribute(CONTENT_OPEN_ATTR)" in bridge
    assert "background:#149d55!important" in bridge
    assert "background:#0f8044!important" in bridge
    assert "background:#5146f6!important" in bridge


def test_file_action_menu_uses_a_color_for_each_action():
    bridge = (ASSETS / "search_investigation_bridge.js").read_text(encoding="utf-8")

    assert "data-lexia-file-action-kind" in bridge
    assert 'ACTION_KIND_ATTR}="open"' in bridge
    assert 'ACTION_KIND_ATTR}="investigate"' in bridge
    assert 'ACTION_KIND_ATTR}="details"' in bridge
    assert 'ACTION_KIND_ATTR}="case"' in bridge
    assert 'ACTION_KIND_ATTR}="ocr"' in bridge
    assert "background:#f4c542!important" in bridge
    assert "background:#8a5a2b!important" in bridge
    assert "background:#e87514!important" in bridge
    assert "button?.matches('.search-delete-file')" in bridge
    assert "button?.matches('[data-lexia-case-link],.lexia-case-link')" in bridge
    assert "classes.includes('ocr')" in bridge
    assert "markActionButtons(actions)" in bridge
