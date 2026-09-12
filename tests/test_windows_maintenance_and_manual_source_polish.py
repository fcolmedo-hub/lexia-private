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
    assert "Analizando cambios: comparando la biblioteca con el catálogo." in source
    assert "Indexando los documentos modificados." in source
    assert "Actualizando el Knowledge Engine" in source
    assert "MutationObserver" not in source
    assert "setInterval(" not in source


def test_duplicate_review_reads_catalog_and_deletes_only_explicit_duplicate():
    source = (ROOT / "services" / "windows_research_manual_sources.py").read_text(encoding="utf-8")
    compile(source, str(ROOT / "services" / "windows_research_manual_sources.py"), "exec")
    assert 'd.duplicate_of IS NOT NULL' in source
    assert 'self.path == "/duplicates"' in source
    assert 'self.path == "/delete-duplicate"' in source
    assert "secure_document_deletion.delete(path)" in source


def test_duplicate_maintenance_panel_opens_duplicate_and_original():
    source = (ASSETS / "windows_maintenance_duplicates.js").read_text(encoding="utf-8")
    assert "LexIA no elimina nada automáticamente" in source
    assert "data-dup-delete" in source
    assert "data-dup-open-original" in source
    assert "Abrir duplicado" in source
    assert "Abrir documento principal" in source
    assert "MutationObserver" not in source
    assert "setInterval(" not in source


def test_manual_sources_share_native_modal_without_replacing_native_sources():
    source = (ASSETS / "windows_research_manual_sources_merge.js").read_text(encoding="utf-8")
    assert "researchSourcesModalList" in source
    assert "lexiaManualResearchModalSources" in source
    assert "lexiaManualResearchSources" in source
    assert "AGREGADA POR EL USUARIO" in source
    assert "accent-color:#169b62" in source
    assert "accent-color:#5146f6" in source
    assert "cloneNode(true)" in source
    assert "Las fuentes halladas por LexIA" in source
    assert "#contextpage #viewSources" in source
    assert "#contextpage #${ADD_BUTTON_ID}" in source
    assert "MutationObserver" not in source
    assert "setInterval(" not in source
