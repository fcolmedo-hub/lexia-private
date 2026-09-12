from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "app" / "ui2" / "assets"


def test_manual_source_service_is_windows_only_and_extends_curated_package():
    source_path = ROOT / "services" / "windows_research_manual_sources.py"
    source = source_path.read_text(encoding="utf-8")

    compile(source, str(source_path), "exec")
    assert 'if sys.platform != "win32"' in source
    assert 'PORT = 8516' in source
    assert 'ThreadingHTTPServer' in source
    assert 'builder.curate_package = curate_with_manual_sources' in source
    assert 'manual_source' in source
    assert 'manual_fragment_id' in source
    assert 'combined.append(source)' in source
    assert 'builder._curate_source_section' in source
    assert '/add-fragment' in source
    assert '_build_manual_fragment' in source
    assert 'DocumentExtractor' not in source
    assert '/add-source' not in source


def test_manual_fragments_allow_multiple_passages_from_same_document():
    source = (ROOT / "services" / "windows_research_manual_sources.py").read_text(encoding="utf-8")

    assert 'uuid.uuid4().hex' in source
    assert '_manual_fragment_key' in source
    assert 'source.page_start' in source
    assert 'source.page_end' in source
    assert 'str(source.text or "")' in source
    assert 'existing_paths' not in source


def test_windows_services_start_and_stop_manual_source_service():
    source = (ROOT / "run_lexia_services.py").read_text(encoding="utf-8")

    assert 'if sys.platform == "win32"' in source
    assert 'start_windows_research_manual_sources' in source
    assert 'stop_windows_research_manual_sources' in source


def test_research_ui_selects_fragment_in_viewer_without_dom_observer():
    source = (ASSETS / "windows_research_manual_sources.js").read_text(encoding="utf-8")

    assert 'Agregar documento conocido' in source
    assert '/api/search-filename' in source
    assert '/api/catalog-text-preview?path=' in source
    assert 'Abrir y seleccionar' in source
    assert 'Agregar selección a la investigación' in source
    assert "http://127.0.0.1:8516" in source
    assert '/add-fragment' in source
    assert 'selected_text:range.text' in source
    assert 'page_start:pages.page_start' in source
    assert 'page_end:pages.page_end' in source
    assert '/add-source' not in source
    assert 'Documento completo' not in source
    assert 'MutationObserver' not in source
    assert 'setInterval' not in source


def test_manual_viewer_stays_open_and_supports_multiple_selections():
    source = (ASSETS / "windows_research_manual_sources.js").read_text(encoding="utf-8")

    assert 'Mantené Shift para sumar otro separado' in source
    assert 'for(const range of selectedRanges)' in source
    assert 'selectedRanges=[]' in source
    assert 'El visor queda abierto para que puedas seleccionar otro pasaje del mismo documento.' in source
    assert 'dialog.close()' not in source[source.index("add.addEventListener('click'"):]


def test_study_type_follows_library_category():
    source = (ASSETS / "windows_research_manual_sources.js").read_text(encoding="utf-8")

    assert "['Doctrina','Legislación']" in source
    assert "return 'Doctrina'" in source
    assert "return 'Fallo judicial'" in source
    assert "return 'Legislación'" in source
    assert "target.closest('#startStudy')" in source
    assert "target.closest('.study-source')" in source


def test_windows_loader_and_case_return_include_manual_fragments():
    loader = (ASSETS / "windows_search_results_polish.js").read_text(encoding="utf-8")
    case_return = (ASSETS / "windows_case_research_return.js").read_text(encoding="utf-8")

    assert 'assets/windows_research_manual_sources.js?v=research-manual-sources-1' in loader
    assert 'data-lexia-windows-research-manual-sources' in loader
    assert 'http://127.0.0.1:8516/sources' in case_return
    assert 'selectedManualSources' in case_return
    assert 'incorporatedManualIds' in case_return
    assert 'manual_research_fragment_id' in case_return
    assert 'page_end:pageEnd' in case_return
