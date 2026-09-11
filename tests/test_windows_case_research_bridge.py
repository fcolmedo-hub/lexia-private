from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "app" / "ui2" / "assets"


def _bridge() -> str:
    return (ASSETS / "windows_case_research_bridge.js").read_text(encoding="utf-8")


def test_bridge_is_loaded_from_windows_runtime_without_continuous_dom_watch():
    loader = (ASSETS / "windows_search_results_polish.js").read_text(encoding="utf-8")
    bridge = _bridge()

    assert "assets/windows_case_research_bridge.js?v=case-research-2" in loader
    assert "data-lexia-windows-case-research-bridge" in loader
    assert "MutationObserver" not in bridge
    assert "setInterval(" not in bridge


def test_own_case_blocks_get_horizontal_investigate_action():
    bridge = _bridge()

    assert "nuestra postura" in bridge
    assert ".argument-block-actions" in bridge
    assert "lexia-case-investigate" in bridge
    assert "flex-direction:row!important" in bridge
    assert "Investigar este fundamento" in bridge


def test_empty_own_position_is_rejected_before_navigation():
    bridge = _bridge()

    assert "Planteá primero el fundamento propio que querés investigar." in bridge
    assert "textarea?.focus()" in bridge


def test_case_research_uses_native_navigation_and_editable_native_fields():
    bridge = _bridge()

    assert "lexiaUI2NavigateGlobal" in bridge
    assert "navigate('contextpage')" in bridge
    assert "sessionStorage.setItem" in bridge
    assert "consulta juridica" in bridge
    assert "objetivo" in bridge
    assert "indicaciones" in bridge
    assert "Los campos siguen siendo editables antes de investigar." in bridge


def test_counterpart_is_only_adversarial_context():
    bridge = _bridge()

    assert "únicamente como contexto adversarial" in bridge
    assert "Buscá refutaciones, distinciones, límites y respuestas" in bridge
    assert "no orientes la investigación a sostener esta tesis" in bridge


def test_subblock_delete_uses_existing_highlight_endpoint_and_keeps_case_file():
    bridge = _bridge()

    assert "/api/cases/block/highlight/delete" in bridge
    assert "highlight_id:highlight.id" in bridge
    assert "El archivo continuará disponible en “Archivos del caso”." in bridge
    assert "highlights.length===evidenceCount" in bridge


def test_bridge_sync_is_bounded_and_event_driven():
    bridge = _bridge()

    assert "[0,80,240,600,1200]" in bridge
    assert "[90,260,600,1100]" in bridge
    assert "document.addEventListener('click'" in bridge
