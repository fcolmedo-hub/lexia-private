from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CSS = ROOT / "app" / "ui2" / "assets" / "desktop_visual_consistency.css"


def test_consistency_layer_is_desktop_scoped_and_conservative():
    source = CSS.read_text(encoding="utf-8")
    assert "@media (min-width: 1200px)" in source
    assert "--lexia-type-page-title: 24px" in source
    assert "--lexia-type-body: 12px" in source
    assert "--lexia-control-height: 36px" in source
    assert "--lexia-control-height-small: 30px" in source
    assert "grid-template" not in source
    assert "position: fixed" not in source
    assert "display: grid" not in source


def test_consistency_layer_covers_existing_dynamic_surfaces():
    source = CSS.read_text(encoding="utf-8")
    for selector in (
        "#lexiaAddManualResearchSource",
        ".result-menu-popover .result-menu-item",
        "#casespage .cases-button",
        "#casespage .argument-evidence",
        ".global-sidebar .nav button",
    ):
        assert selector in source
