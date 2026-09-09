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

    assert "loadInventory" in source
    assert "reservadas'} para revisión/publicación" in source
