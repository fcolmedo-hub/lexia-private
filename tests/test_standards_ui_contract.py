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
    assert "addEventListener('pointerdown'" in source
    assert "dataset.lexiaUserEdited" in source
    assert "cache:'no-store'" in source
    assert "style.setProperty('display','grid','important')" in source


def test_recent_searches_use_the_main_search_popover():
    source = (ROOT / "app/ui2/assets/standards_ui.js").read_text(encoding="utf-8")
    layout = (ROOT / "app/ui2/assets/standards_nav_fix.js").read_text(encoding="utf-8")

    assert "std-primary-row" in layout
    assert "firstGrid.classList.remove('primary')" in layout
    assert "stdHistoryMenu" in source
    assert "query.addEventListener('click'" in source
    assert "||'Todos los estándares'" not in source
    assert "if(!Object.keys(criteria).length)" in source
    assert "saveRecentSearch(criteria);setRecentMenuOpen(false);" in source
    assert "recentMemory=items.slice(0,12)" in source
    assert "dataset.lexiaNativeSearch='2'" in source
    assert "dataset.lexiaNativeSearch==='2'" in layout
    assert "stdRecent" not in source
    assert "Ingresá criterios o dejá los campos vacíos" not in source


def test_normal_search_results_use_three_dot_action_menu():
    bridge = (ROOT / "app/ui2/assets/search_investigation_bridge.js").read_text(encoding="utf-8")
    cases = (ROOT / "app/ui2/assets/case_workspace.js").read_text(encoding="utf-8")

    assert "ensureResultActionMenu(card,actions);" not in bridge
    assert "markActionButtons(actions);" in bridge
    assert "installResultActionMenu(card, actions)" in cases
    assert "actions.querySelector(':scope > .result-action-menu')" in cases
    assert "className: 'result-menu-toggle'" in cases
    assert "textContent: '⋯'" in cases
    assert ".result-card.result-menu-open" in cases
    assert "classList.add('result-menu-open')" in cases
    assert "classList.remove('result-menu-open')" in cases


def test_investigate_action_is_not_relabelled_as_open():
    cases = (ROOT / "app/ui2/assets/case_workspace.js").read_text(encoding="utf-8")

    investigate = cases.index("if (button.matches('.search-investigate-file'))")
    open_file = cases.index("if (button.matches('.search-open-file,.open-source-real'))")
    assert investigate < open_file


def test_filename_results_keep_metadata_inside_the_card():
    cases = (ROOT / "app/ui2/assets/case_workspace.js").read_text(encoding="utf-8")

    assert ".result-card:not(:has(.result-actions>.score))" in cases
    assert "min-height:76px!important" in cases
    assert "min-height:54px!important" in cases
    assert "flex-direction:column!important" in cases
    assert "justify-content:center!important" in cases
    assert ".result-path{display:block!important" in cases
    assert "padding:0!important" in cases
    assert "text-overflow:ellipsis!important" in cases


def test_desktop_launchers_refresh_the_shared_runtime_by_content():
    macos = (ROOT / "app/ui2/macos_desktop.py").read_text(encoding="utf-8")
    windows = (ROOT / "app/ui2/windows_desktop.py").read_text(encoding="utf-8")
    runtime = (ROOT / "app/ui2/assets/app_runtime.js").read_text(encoding="utf-8")

    assert "hashlib.sha256(app_runtime.read_bytes())" in macos
    assert '_upsert_asset_script(\n        patched, app_runtime, "app-runtime"' in windows
    assert "case-47-filename-center" in runtime


def test_action_menu_preserves_requested_background_colors():
    cases = (ROOT / "app/ui2/assets/case_workspace.js").read_text(encoding="utf-8")

    assert "result-menu-open{background:#149d55!important" in cases
    assert "result-menu-investigate{background:#5146f6!important" in cases
    assert "result-menu-info{background:#f4c542!important" in cases
    assert "result-menu-case{background:#8a5a2b!important" in cases
    assert "result-menu-ocr{background:#e87514!important" in cases
    assert "result-menu-delete{background:#c93645!important" in cases
