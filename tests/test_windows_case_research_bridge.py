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


def test_case_to_research_keeps_only_investigation_nav_selected():
    loader = (ASSETS / "windows_search_results_polish.js").read_text(encoding="utf-8")
    nav_fix = (ASSETS / "windows_case_nav_state_fix.js").read_text(encoding="utf-8")

    assert "assets/windows_case_nav_state_fix.js?v=case-nav-1" in loader
    assert "data-lexia-windows-case-nav-state" in loader
    assert "target.closest('.lexia-case-investigate')" in nav_fix
    assert "if(label==='casos')clearSelected(button)" in nav_fix
    assert "selectButton(research)" in nav_fix
    assert "aria-current" in nav_fix
    assert "MutationObserver" not in nav_fix
    assert "setInterval(" not in nav_fix


def test_selected_research_sources_return_to_originating_case_block():
    loader = (ASSETS / "windows_search_results_polish.js").read_text(encoding="utf-8")
    return_flow = (ASSETS / "windows_case_research_return.js").read_text(encoding="utf-8")

    assert "assets/windows_case_research_return.js?v=case-return-1" in loader
    assert "data-lexia-windows-case-research-return" in loader
    assert "#researchSourcesModalList .research-source-check:checked" in return_flow
    assert "/api/research-candidates-result" in return_flow
    assert "/api/cases/link-document" in return_flow
    assert "/api/cases/block/highlight" in return_flow
    assert "block_id:Number(ctx.blockId)" in return_flow
    assert "case_document_id:caseDocumentId" in return_flow
    assert "relation_kind:'fuente de investigación'" in return_flow
    assert "Incorporar al caso y volver" in return_flow
    assert "MutationObserver" not in return_flow
    assert "setInterval(" not in return_flow


def test_return_flow_avoids_duplicate_highlights_on_retry_after_partial_failure():
    return_flow = (ASSETS / "windows_case_research_return.js").read_text(encoding="utf-8")

    assert "incorporatedSourceIndexes" in return_flow
    assert "if(already.has(index))continue" in return_flow
    assert "saveContext(ctx)" in return_flow
