from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
UI2 = ROOT / "app" / "ui2"


def test_mobile_open_preserves_result_location():
    loader = (UI2 / "assets" / "jurisprudence_search.js").read_text(encoding="utf-8")
    html = (UI2 / "index.html").read_text(encoding="utf-8")

    assert "mobileOpenResponse(path,page,snippet)" in loader
    assert "body?.page,body?.snippet" in loader
    assert "JSON.stringify({path:path,page:page,snippet:snippet})" in html
    assert 'data-page="${esc(r.page_start)}"' in html


def test_mobile_viewer_has_real_page_controls_and_server_renderer():
    html = (UI2 / "index.html").read_text(encoding="utf-8")
    server = (UI2 / "server.py").read_text(encoding="utf-8")

    assert "showMobilePagedPreview(path,initialPage,office)" in html
    assert 'data-qv-page="previous"' in html
    assert 'data-qv-page="next"' in html
    assert 'if path == "/api/preview-page-image"' in server
    assert "X-LexIA-Page-Count" in server
