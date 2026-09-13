from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "app" / "ui2" / "assets"


def test_windows_runtime_loads_the_all_routes_responsive_guard():
    loader = (ASSETS / "windows_search_results_polish.js").read_text(encoding="utf-8")

    assert "assets/windows_responsive_layout_guard.js?v=responsive-routes-1" in loader
    assert "data-lexia-windows-responsive-layout-guard" in loader


def test_guard_covers_every_primary_surface_and_short_desktop_height():
    source = (ASSETS / "windows_responsive_layout_guard.js").read_text(encoding="utf-8")

    for selector in (
        "#home",
        "#library",
        "#searchpage",
        "#contextpage",
        "#activitypage",
        "#systempage",
        "#casespage",
        "#maintenance",
        "#lexiaStandardsShell",
    ):
        assert selector in source
    assert "@media (min-width:1200px) and (max-height:950px)" in source
    assert "#researchPanel:not([hidden])" in source
    assert "height:auto!important" in source
    assert "overflow-y:auto!important" in source


def test_guard_is_css_only_and_has_no_continuous_dom_work():
    source = (ASSETS / "windows_responsive_layout_guard.js").read_text(encoding="utf-8")

    assert "MutationObserver" not in source
    assert "setInterval(" not in source
    assert "addEventListener(" not in source
