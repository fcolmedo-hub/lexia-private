from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "app" / "ui2" / "assets"


def test_manual_selection_fix_is_loaded_after_manual_sources():
    loader = (ASSETS / "windows_search_results_polish.js").read_text(encoding="utf-8")

    manual = "assets/windows_research_manual_sources.js?v=research-manual-sources-1"
    fix = "assets/windows_research_manual_selection_fix.js?v=manual-selection-1"
    assert manual in loader
    assert fix in loader
    assert loader.index(manual) < loader.index(fix)
    assert "data-lexia-windows-research-manual-selection-fix" in loader


def test_empty_manual_search_stays_inside_popup():
    source = (ASSETS / "windows_research_manual_selection_fix.js").read_text(encoding="utf-8")

    assert "#'+DIALOG_ID+' [data-manual-search]" in source
    assert "event.stopImmediatePropagation()" in source
    assert "Escribí el nombre o una parte del nombre del archivo" in source
    assert "[data-manual-query]" in source


def test_manual_viewer_accumulates_and_paints_multiple_passages():
    source = (ASSETS / "windows_research_manual_selection_fix.js").read_text(encoding="utf-8")

    assert "state.ranges.concat(selected)" in source
    assert "lexia-manual-selected-mark" in source
    assert "background:#fff0a8" in source
    assert "Cada nueva selección se suma" in source
    assert "state.ranges.splice(index,1)" in source
    assert "data-clear-selection" in source


def test_manual_viewer_sends_each_selected_fragment_with_pages():
    source = (ASSETS / "windows_research_manual_selection_fix.js").read_text(encoding="utf-8")

    assert "for(const range of state.ranges)" in source
    assert "SIDECAR+'/add-fragment'" in source
    assert "selected_text:range.text" in source
    assert "page_start:pages.page_start" in source
    assert "page_end:pages.page_end" in source
    assert "lexiaResearchManualSources?.refresh" in source


def test_manual_selection_fix_has_no_continuous_dom_watch():
    source = (ASSETS / "windows_research_manual_selection_fix.js").read_text(encoding="utf-8")

    assert "MutationObserver" not in source
    assert "setInterval(" not in source
