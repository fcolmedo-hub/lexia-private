from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "app" / "ui2" / "assets"


def test_windows_investigation_fix_is_loaded_without_dom_observer():
    loader = (ASSETS / "windows_search_results_polish.js").read_text(encoding="utf-8")
    fix = (ASSETS / "windows_investigation_layout_fix.js").read_text(encoding="utf-8")

    assert "assets/windows_investigation_layout_fix.js?v=investigation-layout-1" in loader
    assert "lexiaWindowsInvestigationLayout" in loader
    assert "MutationObserver" not in fix


def test_compact_research_action_remains_visible():
    fix = (ASSETS / "windows_investigation_layout_fix.js").read_text(encoding="utf-8")

    assert "@media (min-width:701px) and (max-width:1199px)" in fix
    assert ".context-form" in fix
    assert ".context-actions button" in fix
    assert "display:inline-flex!important" in fix
    assert "visibility:visible!important" in fix
    assert "overflow:visible!important" in fix


def test_source_selector_respects_sidebar_and_compact_viewport():
    fix = (ASSETS / "windows_investigation_layout_fix.js").read_text(encoding="utf-8")

    assert "@media (min-width:1200px)" in fix
    assert ".lexia-sources-modal" in fix
    assert "translate:98px 0!important" in fix
    assert "calc(100vw - var(--global-side,196px) - 28px)" in fix
    assert "@media (max-width:1199px)" in fix
    assert "width:calc(100vw - 20px)!important" in fix


def test_windows_build_does_not_fall_back_to_python_icon():
    script = (ROOT / "scripts" / "rebuild_lexia_app_windows.ps1").read_text(encoding="utf-8")

    assert "@('--icon', 'NONE')" in script
    assert "windows_investigation_layout_fix.js" in script
    assert "se desactivó el icono de Python" in script
