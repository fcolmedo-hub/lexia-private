from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "app" / "ui2" / "assets"


def test_windows_loader_includes_maintenance_and_manual_source_polish():
    source = (ASSETS / "windows_search_results_polish.js").read_text(encoding="utf-8")
    assert "windows_maintenance_status_detail.js?v=maintenance-status-1" in source
    assert "windows_maintenance_duplicates.js?v=maintenance-duplicates-2" in source
    assert "windows_research_manual_sources_merge.js?v=manual-sources-merge-4" in source


def test_autosync_detail_explains_phases_without_continuous_observer():
    source = (ASSETS / "windows_maintenance_status_detail.js").read_text(encoding="utf-8")
    assert "Comparando la biblioteca física con el catálogo" in source
    assert "Indexando los documentos modificados y actualizando sus vectores." in source
    assert "Actualizando el Knowledge Engine con los documentos procesados." in source
    assert "Analizando biblioteca…" in source
    assert "Fase: detección y comparación de cambios" in source
    assert "[0,40,140]" in source
    assert "MutationObserver" not in source
    assert "setInterval(" not in source


def test_duplicate_review_reads_catalog_and_deletes_only_explicit_duplicate():
    source = (ROOT / "services" / "windows_research_manual_sources.py").read_text(encoding="utf-8")
    compile(source, str(ROOT / "services" / "windows_research_manual_sources.py"), "exec")
    assert 'd.duplicate_of IS NOT NULL' in source
    assert 'self.path == "/duplicates"' in source
    assert 'self.path == "/delete-duplicate"' in source
    assert "secure_document_deletion.delete(path)" in source


def test_duplicate_maintenance_panel_requires_user_delete_action():
    source = (ASSETS / "windows_maintenance_duplicates.js").read_text(encoding="utf-8")
    assert "LexIA no elimina nada automáticamente" in source
    assert "data-dup-delete" in source
    assert "data-dup-open-original" in source
    assert "Abrir duplicado" in source
    assert "MutationObserver" not in source
    assert "setInterval(" not in source


def test_manual_sources_share_native_renderer_scroll_and_green_identity():
    source = (ASSETS / "windows_research_manual_sources_merge.js").read_text(encoding="utf-8")
    assert "researchSourcesModalList" in source
    assert "researchSourceList" in source
    assert "sidecar('/sources')" in source
    assert "renderUnifiedCard" in source
    assert "lexia-unified-source-card" in source
    assert "lexia-source-automatic" in source
    assert "lexia-source-manual" in source
    assert "nativeClass:placement==='modal'?'lexia-source-choice':'source-item'" in source
    assert "nativeClass:'lexia-source-choice'" in source
    assert "color:#168054" in source
    assert "accent-color:#169b62" in source
    assert "background:#9a3b8f" in source
    assert "renderPlacement(document.getElementById(MODAL_LIST_ID),sources,'modal')" in source
    assert "renderPlacement(document.getElementById(MAIN_LIST_ID),sources,'main')" in source
    assert "cleanupLegacyMainContainer" in source
    assert "cloneNode(true)" not in source
    assert "MutationObserver" not in source
    assert "setInterval(" not in source


def test_manual_and_automatic_sources_are_merged_before_visual_numbering():
    source = (ASSETS / "windows_research_manual_sources_merge.js").read_text(encoding="utf-8")

    assert "const automaticSources=directAutomaticCards(container)" in source
    assert "const manualSources=(sources||[])" in source
    assert "const finalSources=automaticSources.concat(manualSources)" in source
    assert "renderUnifiedCard(entry.parts,index+1,entry.kind)" in source
    assert "nativeSourceCount" not in source
    assert "startNumber" not in source


def test_native_checkbox_rerender_restores_cached_manual_sources_event_driven():
    source = (ASSETS / "windows_research_manual_sources_merge.js").read_text(encoding="utf-8")

    assert "let manualSourcesCache=[]" in source
    assert "renderMergedLists(manualSourcesCache)" in source
    assert "if(target.matches('.research-source-check'))" in source
    assert "refreshSoon()" in source
    assert "window.setTimeout(()=>{refreshQueued=false;merge();},0)" in source
    assert "MutationObserver" not in source
    assert "setInterval(" not in source


def test_unified_source_cards_reserve_equal_dimensions_and_button_sizes():
    source = (ASSETS / "windows_research_manual_sources_merge.js").read_text(encoding="utf-8")

    assert "height:116px!important;min-height:116px!important" in source
    assert "grid-template-columns:18px 26px minmax(0,1fr) 76px" in source
    assert "width:76px!important;min-width:76px!important;height:24px!important;min-height:24px!important" in source
    assert "background:#eeecff!important;color:#5146f6!important" in source
    assert "background:#e7f6ed!important;color:#168054!important" in source


def test_manual_cards_expose_only_the_requested_manual_action():
    source = (ASSETS / "windows_research_manual_sources_merge.js").read_text(encoding="utf-8")

    assert "remove.textContent='Quitar'" in source
    assert "lexia-manual-native-remove" in source
    assert "data-lexia-case-link" not in source
    assert "data-lexia-ocr-reprocess" not in source


def test_native_source_text_is_constrained_inside_cards():
    source = (ASSETS / "windows_research_manual_sources_merge.js").read_text(encoding="utf-8")
    assert "overflow-wrap:anywhere" in source
    assert "max-width:100%" in source
    assert "min-width:0" in source


def test_manual_search_keeps_investigation_as_modal_background():
    source = (ASSETS / "windows_research_manual_sources_merge.js").read_text(encoding="utf-8")
    assert "body.lexia-manual-search-open #searchpage{display:none!important}" in source
    assert "body.lexia-manual-search-open #contextpage{display:block!important}" in source
    assert "keepInvestigationBackground" in source
