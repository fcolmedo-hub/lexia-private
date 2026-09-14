from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "app" / "ui2" / "assets"


def _bridge() -> str:
    return (ASSETS / "windows_case_research_bridge.js").read_text(encoding="utf-8")


def test_bridge_is_loaded_from_windows_runtime_without_continuous_dom_watch():
    loader = (ASSETS / "windows_search_results_polish.js").read_text(encoding="utf-8")
    bridge = _bridge()

    assert "assets/windows_case_research_bridge.js?v=case-research-9" in loader
    assert "data-lexia-windows-case-research-bridge" in loader
    assert "MutationObserver" not in bridge
    assert "setInterval(" not in bridge


def test_own_case_blocks_get_vertical_add_investigate_delete_actions():
    bridge = _bridge()

    assert "nuestra postura" in bridge
    assert ".argument-block-actions" in bridge
    assert "lexia-case-investigate" in bridge
    assert "flex-direction:column!important" in bridge
    assert "width:24px!important" in bridge
    assert "actions.insertBefore(button,remove)" in bridge
    assert "+ / lupa / papelera" in bridge
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

    assert "querySelectorAll('.argument-section')" in bridge
    assert "resolved?.node?.blocks?.contraparte" in bridge
    assert "counterpartText(article,base.blockIndex,base)" in bridge


def test_subblock_delete_uses_existing_highlight_endpoint_and_keeps_case_file():
    bridge = _bridge()
    workspace = (ASSETS / "case_workspace.js").read_text(encoding="utf-8")

    assert "/api/cases/block/highlight/delete" in bridge
    assert "highlight_id:highlight.id" in bridge
    assert "El archivo continuará disponible en “Archivos del caso”." in bridge
    assert "highlights.length===evidenceCount" in bridge
    assert "const row = el('div', {className: 'lexia-case-evidence-row'}, excerpt)" in workspace
    assert "Eliminar esta fuente del bloque" in workspace
    assert "highlight_id: highlight.id" in workspace
    assert "body.append(row)" in workspace


def test_windows_case_flag_is_available_before_async_bridge_download():
    loader = (ASSETS / "windows_search_results_polish.js").read_text(encoding="utf-8")

    assert "window.__lexiaWindowsCaseEvidenceSelectionV2 = true" in loader


def test_bridge_sync_is_bounded_and_event_driven():
    bridge = _bridge()

    assert "[0,80,240,600,1200]" in bridge
    assert "[90,260,600,1100]" in bridge
    assert "document.addEventListener('click'" in bridge


def test_case_evidence_viewer_exposes_multiple_selection_chips_directly():
    bridge = _bridge()
    workspace = (ASSETS / "case_workspace.js").read_text(encoding="utf-8")

    assert "simplifyEvidenceSelectionDialog" in bridge
    assert "window.__lexiaWindowsCaseEvidenceSelectionV2=true" in bridge
    assert "Guardar selecciones" in bridge
    assert "if(label==='cambiar seleccion')button.remove()" in bridge
    assert ".evidence-selection-chip" in bridge
    assert "flex:0 0 auto!important" in bridge
    assert "min-height:30px!important;max-height:74px!important" in bridge
    assert "selectedRanges = [existingRange]" in workspace
    assert "windowsMultiSelection ? 'Selección ' : 'Pasaje '" in workspace
    assert "capture(windowsMultiSelection || event.shiftKey" in workspace
    assert "cada nueva selección se suma automáticamente" in workspace
    assert "/api/cases/block/highlight/delete" in workspace


def test_case_tree_state_survives_navigation_and_research_return_reopens_origin():
    workspace = (ASSETS / "case_workspace.js").read_text(encoding="utf-8")
    return_flow = (ASSETS / "windows_case_research_return.js").read_text(encoding="utf-8")

    assert "WINDOWS_CASE_UI_STATE_KEY" in workspace
    assert "persistCaseUiState(snapshot.case.id)" in workspace
    assert "restoreCaseUiState(caseId, currentCase.nodes || [])" in workspace
    assert "window.lexiaCaseWorkspaceFocusQuestion = focusCaseQuestion" in workspace
    assert "window.lexiaCaseWorkspaceFocusQuestion?.(ctx.caseId,ctx.nodeId)" in return_flow


def test_case_block_renders_every_saved_highlight_with_a_stable_identity():
    workspace = (ASSETS / "case_workspace.js").read_text(encoding="utf-8")

    assert "orderedBlockHighlights(block.highlights).forEach(highlight =>" in workspace
    assert "'data-highlight-id': String(highlight.id || '')" in workspace
    assert "for (let index = 0; index < selectedRanges.length; index += 1)" in workspace
    assert "/api/cases/block/highlight'" in workspace


def test_case_highlights_are_grouped_by_file_then_selection_order():
    workspace = (ASSETS / "case_workspace.js").read_text(encoding="utf-8")

    assert "function orderedBlockHighlights(values)" in workspace
    assert "const documentOrder = new Map()" in workspace
    assert "highlight.case_document_id" in workspace
    assert "left.documentOrder - right.documentOrder || left.index - right.index" in workspace
    assert "orderedBlockHighlights(block.highlights).map" in workspace


def test_case_to_research_keeps_only_investigation_nav_selected():
    loader = (ASSETS / "windows_search_results_polish.js").read_text(encoding="utf-8")
    nav_fix = (ASSETS / "windows_case_nav_state_fix.js").read_text(encoding="utf-8")

    assert "assets/windows_case_nav_state_fix.js?v=case-nav-2" in loader
    assert "data-lexia-windows-case-nav-state" in loader
    assert "target.closest('.lexia-case-investigate')" in nav_fix
    assert "if(label==='casos')clearSelected(button)" in nav_fix
    assert "selectButton(research)" in nav_fix
    assert "aria-current" in nav_fix
    assert "lexia-windows-cases-open" in nav_fix
    assert "overflow:hidden!important" in nav_fix
    assert "setCasesScrollLock(label==='casos')" in nav_fix
    assert "MutationObserver" not in nav_fix
    assert "setInterval(" not in nav_fix


def test_selected_research_sources_return_to_originating_case_block():
    loader = (ASSETS / "windows_search_results_polish.js").read_text(encoding="utf-8")
    return_flow = (ASSETS / "windows_case_research_return.js").read_text(encoding="utf-8")

    assert "assets/windows_case_research_return.js?v=case-return-4" in loader
    assert "data-lexia-windows-case-research-return" in loader
    assert "#researchSourcesModalList .research-source-check:checked" in return_flow
    assert "/api/research-candidates-result" in return_flow
    assert "/api/cases/link-document" in return_flow
    assert "/api/cases/block/highlight" in return_flow
    assert "block_id:Number(ctx.blockId)" in return_flow
    assert "case_document_id:caseDocumentId" in return_flow
    assert "relation_kind:'fuente de investigación'" in return_flow
    assert "Cargar fuentes en el subbloque del caso" in return_flow
    assert "build.hidden=linked" in return_flow
    assert "#contextpage .context-side>.lexia-sources-foot" in return_flow
    assert "MutationObserver" not in return_flow
    assert "setInterval(" not in return_flow


def test_return_button_is_revealed_after_case_context_exists():
    return_flow = (ASSETS / "windows_case_research_return.js").read_text(encoding="utf-8")

    assert "#startContext" in return_flow
    assert "label==='investigar'||label==='revisar fuentes'" in return_flow
    assert "[0,100,350,900,1700,3000,5000]" in return_flow
    assert "target?.matches('.research-source-check,.lexia-manual-source-check')" in return_flow
    assert "const linked=Boolean(ctx?.caseId&&ctx?.blockId)" in return_flow
    assert "button.hidden=!linked" in return_flow
    assert "build.hidden=linked" in return_flow


def test_return_flow_avoids_duplicate_highlights_on_retry_after_partial_failure():
    return_flow = (ASSETS / "windows_case_research_return.js").read_text(encoding="utf-8")

    assert "incorporatedSourceIndexes" in return_flow
    assert "if(already.has(index))continue" in return_flow
    assert "saveContext(ctx)" in return_flow


def test_windows_research_transport_retries_only_safe_get_status_and_result_calls():
    loader = (ASSETS / "windows_search_results_polish.js").read_text(encoding="utf-8")
    resilience = (ASSETS / "windows_research_transport_resilience.js").read_text(encoding="utf-8")

    assert "assets/windows_research_transport_resilience.js?v=research-resilience-1" in loader
    assert "data-lexia-windows-research-resilience" in loader
    assert "requestMethod(input,init)!=='GET'" in resilience
    assert "research-candidates" in resilience
    assert "research-package" in resilience
    assert "retryableStatus" in resilience
    assert "[408,429,502,503,504]" in resilience
    assert "retryDelays=[0,250,700,1500]" in resilience
    assert "emptyCompletedResult" in resilience
    assert "research-candidates-start" not in resilience
    assert "MutationObserver" not in resilience
    assert "setInterval(" not in resilience


def test_new_research_leaves_case_context_and_restores_ai_action():
    bridge = _bridge()
    return_flow = (ASSETS / "windows_case_research_return.js").read_text(
        encoding="utf-8"
    )

    assert "target.closest('#newContext')" in bridge
    assert "document.getElementById('lexiaCaseResearchOrigin')?.remove()" in bridge
    assert "window.lexiaCaseResearchReturn?.sync?.()" in bridge
    assert "#reviewResearchSources,#newContext" in return_flow
    assert "build.hidden=linked" in return_flow
