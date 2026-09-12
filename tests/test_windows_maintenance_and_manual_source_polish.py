from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "app" / "ui2" / "assets"


def test_windows_loader_includes_maintenance_and_manual_source_polish():
    source = (ASSETS / "windows_search_results_polish.js").read_text(encoding="utf-8")
    assert "windows_maintenance_status_detail.js?v=maintenance-status-1" in source
    assert "windows_maintenance_duplicates.js?v=maintenance-duplicates-2" in source
    assert "windows_research_manual_sources_merge.js?v=manual-sources-merge-2" in source


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


def test_manual_sources_are_loaded_directly_into_native_source_list_with_green_identity():
    source = (ASSETS / "windows_research_manual_sources_merge.js").read_text(encoding="utf-8")
    assert "researchSourcesModalList" in source
    assert "sidecar('/sources')" in source
    assert "FUENTE ${nativeCount+index+1} · AGREGADA POR EL USUARIO" in source
    assert "accent-color:#169b62" in source
    assert "accent-color:#5146f6" in source
    assert "list.appendChild(label)" in source
    assert "cloneNode(true)" not in source
    assert "MutationObserver" not in source
    assert "setInterval(" not in source


def test_manual_search_keeps_investigation_as_modal_background():
    source = (ASSETS / "windows_research_manual_sources_merge.js").read_text(encoding="utf-8")
    assert "body.lexia-manual-search-open #searchpage{display:none!important}" in source
    assert "body.lexia-manual-search-open #contextpage{display:block!important}" in source
    assert "keepInvestigationBackground" in source
