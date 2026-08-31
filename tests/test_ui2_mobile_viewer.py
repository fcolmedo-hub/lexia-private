import importlib.util
import os
from pathlib import Path
import sys
import types
from unittest.mock import patch

import fitz


ROOT = Path(__file__).resolve().parents[1]
UI2 = ROOT / "app" / "ui2"


def test_mobile_open_preserves_result_location():
    loader = (UI2 / "assets" / "jurisprudence_search.js").read_text(encoding="utf-8")
    html = (UI2 / "index.html").read_text(encoding="utf-8")

    assert "mobileOpenResponse(path,page,snippet)" in loader
    assert "body?.page,body?.snippet" in loader
    assert "JSON.stringify({path:path,page:page,snippet:snippet})" in html
    assert 'data-page="${esc(r.page_start)}"' in html


def test_mobile_search_prevents_and_recovers_focus_zoom():
    loader = (UI2 / "assets" / "jurisprudence_search.js").read_text(encoding="utf-8")

    assert "viewport.id='lexiaViewport'" in loader
    assert "el.type='search'" in loader
    assert "el.setAttribute('inputmode','search')" in loader
    assert "el.style.setProperty('font-size','16px','important')" in loader
    assert "resetViewportZoom" in loader
    assert "minimum-scale=1,maximum-scale=1" in loader
    assert "__lexiaMobileViewportResetInstalled" in loader
    for launcher in ("launch_ui2.py", "macos_desktop.py", "windows_desktop.py"):
        source = (UI2 / launcher).read_text(encoding="utf-8")
        assert "jurisprudence_search.js?v=juris-mobile-5" in source


def test_mobile_recent_history_activates_before_pointerout_closes_panel():
    loader = (UI2 / "assets" / "jurisprudence_search.js").read_text(encoding="utf-8")

    assert "installMobileRecentHistoryFix" in loader
    assert "#searchRecentHistory button[data-query]" in loader
    assert "window.addEventListener('pointerdown'" in loader
    assert "window.addEventListener('pointermove'" in loader
    assert "window.addEventListener('pointerup'" in loader
    assert "Math.hypot(dx,dy)>12" in loader
    recent_start = loader.index("function installMobileRecentHistoryFix")
    down_start = loader.index("window.addEventListener('pointerdown'", recent_start)
    move_start = loader.index("window.addEventListener('pointermove'", down_start)
    assert "activate(" not in loader[down_start:move_start]
    assert "input.value=String(button.dataset.query||'')" in loader
    assert "window.lexiaSearch320Run?.()" in loader


def test_home_search_always_switches_to_filename_before_running():
    loader = (UI2 / "assets" / "jurisprudence_search.js").read_text(encoding="utf-8")

    assert "installHomeFilenameSearchFix" in loader
    assert "#homeQuickSearchButton" in loader
    assert "window.lexiaSearch320SetMode?.('filename')" in loader
    mode_position = loader.index("window.lexiaSearch320SetMode?.('filename')")
    query_position = loader.index("legal.value=query", mode_position)
    run_position = loader.index("window.lexiaSearch320Run?.()", query_position)
    assert mode_position < query_position < run_position


def test_mobile_viewer_has_real_page_controls_and_server_renderer():
    loader = (UI2 / "assets" / "jurisprudence_search.js").read_text(encoding="utf-8")
    server = (UI2 / "server.py").read_text(encoding="utf-8")

    assert "installMobileViewerFix" in loader
    assert 'data-qv-page="previous"' in loader
    assert 'data-qv-page="next"' in loader
    assert "touchstart" in loader
    assert "data-qv-retry" in loader
    assert "locate=1&snippet=" in loader
    assert 'if path == "/api/preview-page-image"' in server
    assert "X-LexIA-Page-Count" in server


def test_mobile_renderer_locates_snippet_and_renders_real_page(tmp_path):
    module_name = "lexia_ui2_server_mobile_test"
    spec = importlib.util.spec_from_file_location(module_name, UI2 / "server.py")
    assert spec and spec.loader
    server = importlib.util.module_from_spec(spec)
    previous_cwd = Path.cwd()
    sys.path.insert(0, str(UI2))
    backend_stub = types.ModuleType("backend")
    backend_stub.LiveReadOnlyAdapter = type("LiveReadOnlyAdapter", (), {})
    runtime_stub = types.ModuleType("search_runtime")
    runtime_stub.SearchRuntime = type("SearchRuntime", (), {})
    boolean_query_stub = types.ModuleType("search.boolean_query")
    boolean_query_stub.parse_boolean_query = lambda value: value
    boolean_query_stub.BooleanQuerySyntaxError = ValueError
    boolean_search_stub = types.ModuleType("search.boolean_document_search")
    boolean_search_stub.search_boolean_documents = lambda *args, **kwargs: []
    try:
        with patch.dict(sys.modules, {
            "backend": backend_stub,
            "search_runtime": runtime_stub,
            "search.boolean_query": boolean_query_stub,
            "search.boolean_document_search": boolean_search_stub,
        }):
            spec.loader.exec_module(server)
    finally:
        os.chdir(previous_cwd)
        sys.path.remove(str(UI2))

    pdf_path = tmp_path / "mobile-viewer.pdf"
    document = fitz.open()
    for text in ("primera página", "pasaje jurídico inequívoco", "tercera página"):
        page = document.new_page()
        page.insert_text((72, 72), text)
    document.save(pdf_path)
    document.close()

    with patch.object(server, "_resolve_catalog_document", return_value=str(pdf_path)):
        png, selected, total = server._preview_page_png(
            str(pdf_path),
            page=1,
            snippet="pasaje jurídico inequívoco",
            locate=True,
        )

    assert png.startswith(b"\x89PNG")
    assert selected == 2
    assert total == 3
