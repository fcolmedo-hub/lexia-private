from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PARITY = ROOT / "app" / "ui2" / "assets" / "macos_desktop_parity.js"


def test_macos_home_uses_only_inner_recent_scroll() -> None:
    source = PARITY.read_text(encoding="utf-8")
    assert "#home {" in source
    assert "overflow-y:hidden!important" in source
    assert "#home .hr-lower>.hr-card .hr-scroll-list" in source
    assert "overflow-y:auto!important" in source
    assert "#home .hr-lower {" in source
    assert "flex:1 1 0!important" in source


def test_macos_home_recent_icons_are_fixed_svg_assets() -> None:
    source = PARITY.read_text(encoding="utf-8")
    assert "Iconos deterministas" in source
    assert source.count("background-image:url(\"data:image/svg+xml") == 2
    assert "nth-child(1) .hr-row>i" in source
    assert "nth-child(2) .hr-row>i" in source
    assert ".hr-row>i svg" in source
    assert "display:none!important" in source


def test_home_fix_does_not_add_observers_or_polling() -> None:
    source = PARITY.read_text(encoding="utf-8")
    assert "MutationObserver" not in source
    assert "setInterval" not in source
