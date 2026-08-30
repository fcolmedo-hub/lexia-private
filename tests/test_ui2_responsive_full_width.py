from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "app" / "ui2" / "assets"


def test_drawer_breakpoint_does_not_reserve_desktop_sidebar_width():
    css = (ASSETS / "responsive_shell.css").read_text(encoding="utf-8")

    assert "@media (max-width:1199px)" in css
    assert "@media (min-width:901px) and (max-width:1199px)" not in css
    assert "--global-side:196px!important" not in css

    for route in ("home", "library", "searchpage", "contextpage", "activitypage", "systempage"):
        assert f"html body #{route}" in css


def test_responsive_assets_share_the_same_breakpoint_and_cache_version():
    runtime = (ASSETS / "home_width_runtime.js").read_text(encoding="utf-8")
    loader = (ASSETS / "jurisprudence_search.js").read_text(encoding="utf-8")

    assert "window.innerWidth<=1199" in runtime
    assert "responsive_shell.css?v=ui2-3.4.4-search-width" in loader


def test_desktop_search_uses_exact_viewport_remainder():
    css = (ASSETS / "responsive_shell.css").read_text(encoding="utf-8")

    assert "@media (min-width:1200px)" in css
    assert "html body #searchpage" in css
    assert "width:calc(100vw - var(--global-side))!important" in css
    assert "html body #searchpage .results-wrap" in css
