import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "app" / "ui2" / "assets"


def test_macos_launcher_injects_versioned_desktop_ui_foundation():
    launcher = (ROOT / "app" / "ui2" / "macos_desktop.py").read_text(encoding="utf-8")

    assert 'desktop_ui_foundation = here / "assets" / "desktop_ui_foundation.css"' in launcher
    assert 'hashlib.sha256(desktop_ui_foundation.read_bytes()).hexdigest()[:12]' in launcher
    assert 'assets/desktop_ui_foundation.css?v=desktop-ui-' in launcher


def test_desktop_ui_foundation_is_scoped_and_uses_a_small_type_scale():
    css = (ASSETS / "desktop_ui_foundation.css").read_text(encoding="utf-8")

    assert 'html[data-lexia-app="1"]' in css
    assert "--lexia-font-page-title: 24px" in css
    assert "--lexia-font-body: 13px" in css
    assert "--lexia-font-caption: 11px" in css
    assert "--lexia-control-height: 38px" in css
    assert "--lexia-control-compact-height: 34px" in css

    pixel_sizes = [
        float(value)
        for value in re.findall(r"--lexia-font-[\w-]+:\s*(\d+(?:\.\d+)?)px", css)
    ]
    assert pixel_sizes
    assert min(pixel_sizes) >= 11


def test_desktop_ui_foundation_covers_the_main_modules_without_layout_rewrite():
    css = (ASSETS / "desktop_ui_foundation.css").read_text(encoding="utf-8")

    for selector in (
        "#searchpage .result-actions button",
        "#contextpage .source-actions button",
        "#casespage .cases-button",
        "#lexiaStandardsShell .std-btn",
        "#maintenance .maint-btn",
    ):
        assert selector in css

    assert "grid-template-columns" not in css
    assert "position: fixed" not in css
    assert "100vh" not in css
