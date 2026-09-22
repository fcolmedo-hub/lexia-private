from __future__ import annotations

import ast
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LAUNCHER = ROOT / "app" / "ui2" / "macos_desktop.py"
FOUNDATION = ROOT / "app" / "ui2" / "assets" / "desktop_ui_foundation.css"
LAYOUT = ROOT / "app" / "ui2" / "assets" / "desktop_ui_layout_phase2.css"


def test_launcher_loads_phase2_after_foundation_with_content_version() -> None:
    source = LAUNCHER.read_text(encoding="utf-8")
    ast.parse(source)
    assert "desktop_ui_layout_phase2.css?v=desktop-ui-layout-{version}" in source
    assert "hashlib.sha256(desktop_ui_layout.read_bytes())" in source
    assert source.index("desktop_ui_foundation.css?v=") < source.index(
        "desktop_ui_layout_phase2.css?v="
    )


def test_phase2_is_mac_app_scoped_and_covers_principal_views() -> None:
    css = LAYOUT.read_text(encoding="utf-8")
    required = (
        '#home .hr-metrics',
        '#home .hr-lower .hr-card',
        '#searchpage .lexia-navigator-view',
        '#contextpage:not(.lexia-source-review) .context-grid',
        '#contextpage.lexia-source-review .context-grid',
        '#casespage .workspace-layout',
        '#lexiaStandardsShell .std-wrap',
        '#maintenance .maint-grid',
    )
    for selector in required:
        assert selector in css

    uncommented = re.sub(r"/\*.*?\*/", "", css, flags=re.DOTALL)
    selector_groups = [
        match.group(2)
        for match in re.finditer(r"(^|})\s*([^@][^{]+)\{", uncommented)
    ]
    assert selector_groups
    for group in selector_groups:
        for selector in group.split(","):
            selector = selector.strip()
            if selector:
                assert selector.startswith('html[data-lexia-app="1"]')


def test_phase2_changes_geometry_and_stays_css_only() -> None:
    css = LAYOUT.read_text(encoding="utf-8")
    assert "height: 168px" in css
    assert "height: clamp(270px, 34vh, 330px)" in css
    assert "max-width: none" in css
    assert "@media (min-width: 1200px)" in css
    assert "@media (max-width: 1199px)" in css
    assert css.count("{") == css.count("}")
    assert "MutationObserver" not in css
    assert "setInterval" not in css
    assert "position: fixed" not in css
    assert "<script" not in css


def test_phase2_is_an_independent_reversible_layer() -> None:
    assert FOUNDATION.exists()
    assert LAYOUT.exists()
    assert FOUNDATION != LAYOUT
    launcher = LAUNCHER.read_text(encoding="utf-8")
    assert launcher.count("desktop_ui_layout_phase2.css") == 2
