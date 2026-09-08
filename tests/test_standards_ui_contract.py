from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_search_controls_and_empty_initial_state():
    source = (ROOT / "app/ui2/assets/standards_ui.js").read_text(encoding="utf-8")

    assert 'id="stdClear" type="button"' in source
    assert 'id="stdSearch" type="button"' in source
    assert '<div id="stdResults"></div>' in source
    assert "function resetSearch()" in source
    assert "node.querySelector('#stdResults')?.replaceChildren()" in source
    assert "api('/api/search?'+p.toString())" in source
    assert ".std-layout{display:none" in source
    assert ".std-layout.has-results{display:grid}" in source
    assert "layout?.classList.add('has-results')" in source
    assert "event.target.closest?.('#globalSidebar .nav button,.sidebar .nav button')" in source
    assert "window.lexiaStandardsSearch=search" in source
    assert "window.lexiaStandardsResetSearch=resetSearch" in source


def test_recent_searches_use_the_main_search_popover():
    source = (ROOT / "app/ui2/assets/standards_nav_fix.js").read_text(encoding="utf-8")

    assert "std-primary-row" in source
    assert "firstGrid.classList.remove('primary')" in source
    assert "stdHistoryMenu" in source
    assert "q.addEventListener('click',toggleHistory)" in source
    assert "||'Todos los estándares'" in source
    assert "toggle.hidden=false" in source
    assert "function installActionRouter()" in source
    assert "target.closest('#stdSearch')" in source
    assert "target.closest('#stdHistoryToggle,#stdQ')" in source
    assert "recentMemory=items" in source
    assert "stdRecent" not in source
    assert "Ingresá criterios o dejá los campos vacíos" not in source
