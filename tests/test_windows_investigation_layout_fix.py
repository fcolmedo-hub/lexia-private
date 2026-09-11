import base64
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "app" / "ui2" / "assets"


def test_windows_investigation_fix_is_loaded_without_dom_observer():
    loader = (ASSETS / "windows_search_results_polish.js").read_text(encoding="utf-8")
    fix = (ASSETS / "windows_investigation_layout_fix.js").read_text(encoding="utf-8")

    assert "assets/windows_investigation_layout_fix.js?v=investigation-layout-2" in loader
    assert "lexiaWindowsInvestigationLayout" in loader
    assert "MutationObserver" not in fix


def test_compact_research_action_is_moved_to_visible_dock():
    fix = (ASSETS / "windows_investigation_layout_fix.js").read_text(encoding="utf-8")

    assert "lexiaWindowsResearchActionDock" in fix
    assert "normalize(button.textContent)!=='investigar'" in fix
    assert "window.innerWidth>1199" in fix
    assert "dock.appendChild(button)" in fix
    assert "window.addEventListener('resize'" in fix
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


def test_windows_build_uses_bundled_lexia_icon_payload():
    script = (ROOT / "scripts" / "rebuild_lexia_app_windows.ps1").read_text(encoding="utf-8")
    encoded = (ROOT / "assets" / "LexIA.ico.b64").read_text(encoding="ascii").strip()
    payload = base64.b64decode(encoded, validate=True)

    assert payload[:4] == b"\x00\x00\x01\x00"
    assert len(payload) > 1000
    assert "assets\\LexIA.ico.b64" in script
    assert "FromBase64String" in script
    assert "$GeneratedIcon" in script
    assert "@('--icon', $Icon)" in script
    assert "windows_investigation_layout_fix.js" in script
