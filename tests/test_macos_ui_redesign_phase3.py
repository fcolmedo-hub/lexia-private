from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LAUNCHER = ROOT / "app" / "ui2" / "macos_desktop.py"
REDESIGN = ROOT / "app" / "ui2" / "assets" / "desktop_ui_redesign_phase3.css"


def test_macos_launcher_loads_phase3_after_phase2() -> None:
    source = LAUNCHER.read_text(encoding="utf-8")
    ast.parse(source)
    assert "hashlib.sha256(desktop_ui_redesign.read_bytes())" in source
    assert "desktop_ui_redesign_phase3.css?v=desktop-ui-redesign-{version}" in source
    assert source.index("desktop_ui_layout_phase2.css?v=") < source.index(
        "desktop_ui_redesign_phase3.css?v="
    )


def test_phase3_has_perceptible_changes_for_all_main_views() -> None:
    css = REDESIGN.read_text(encoding="utf-8")
    required = (
        "#globalSidebar.global-sidebar",
        "#home .hr-search",
        "#home .hr-metrics article::before",
        "#searchpage .lexia-nav-panel",
        "#contextpage .investigation-tabs",
        "#casespage .workspace-layout",
        "#lexiaStandardsShell .std-search",
        "#maintenance .maint-tabs",
    )
    for selector in required:
        assert selector in css
    assert "--global-side: clamp(188px, 13vw, 208px)" in css
    assert "--lexia-shadow-card:" in css
    assert "font-size: 28px" in css
    assert "grid-template-columns: minmax(0, 1.65fr)" in css


def test_phase3_remains_scoped_css_only_and_reversible() -> None:
    css = REDESIGN.read_text(encoding="utf-8")
    assert css.count("{") == css.count("}")
    assert css.count('html[data-lexia-app="1"]') >= 40
    assert "MutationObserver" not in css
    assert "setInterval" not in css
    assert "<script" not in css
    assert "position: fixed" not in css
    launcher = LAUNCHER.read_text(encoding="utf-8")
    assert launcher.count("desktop_ui_redesign_phase3.css") == 3
