from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
UI = ROOT / "app" / "ui2" / "assets" / "standards_ui.js"


def test_standards_ui_uses_responsive_server_pagination():
    source = UI.read_text(encoding="utf-8")

    assert "pageSizeForViewport" in source
    assert "p.set('offset'" in source
    assert "data-std-page" in source
    assert "p.set('limit','200')" not in source


def test_standards_ui_replaces_graph_with_direct_relations():
    source = UI.read_text(encoding="utf-8")

    assert "Relaciones directas" in source
    assert "stdGraphBtn" not in source
    assert "Grafo de relaciones" not in source


def test_standards_ui_explains_visible_and_reserved_counts():
    source = UI.read_text(encoding="utf-8")
    nav_source = (ROOT / "app" / "ui2" / "assets" / "standards_nav_fix.js").read_text(
        encoding="utf-8"
    )

    assert "loadInventory" in source
    assert "stdReservedControl" in source
    assert "Revisar reservadas" in source
    assert "reservedControl.textContent" in source
    assert "stdReservedControl" in nav_source
    assert "queryWrap,clear,search,reserved,add" in nav_source


def test_standards_ui_has_reserved_review_workflow():
    source = UI.read_text(encoding="utf-8")

    assert "reservedQueue" in source
    assert "reservedDetail" in source
    assert "data-publication=\"publish\"" in source
    assert "data-publication=\"reserve\"" in source
    assert "data-publication=\"reject\"" in source
    assert "/api/publication-decision" in source
    assert "/api/standard-citation" in source
    assert "saveReservedCitation" in source
    assert "cita literal y su página" in source
    assert "disabled title=\"Completá una cita literal con página\"" in source
    assert "lexiaStandardsLoadInventory=loadInventory" in source


def test_standards_ui_never_stores_empty_recent_searches():
    source = UI.read_text(encoding="utf-8")
    nav_fix = (ROOT / "app" / "ui2" / "assets" / "standards_nav_fix.js").read_text(
        encoding="utf-8"
    )

    assert "if(!Object.keys(criteria).length)" in source
    assert "if(!Object.keys(criteria).length)" in nav_fix
    assert "||'Todos los estándares'" not in source
    assert "||'Todos los estándares'" not in nav_fix
    assert "clean.length!==raw.length" in nav_fix
    assert "lexiaStandardsLoadInventory" in nav_fix
