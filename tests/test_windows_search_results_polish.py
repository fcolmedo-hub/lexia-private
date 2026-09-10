from pathlib import Path

from app.ui2.windows_desktop import ensure_ui_assets


ROOT = Path(__file__).resolve().parents[1]


def test_windows_search_polish_compensates_webview_content_metrics() -> None:
    source = (
        ROOT / "app/ui2/assets/windows_search_results_polish.js"
    ).read_text(encoding="utf-8")

    assert "lexia-windows-search-polish" in source
    assert ".result-card:not(:has(.result-actions > .score))" in source
    assert "font-weight:600!important" in source
    assert ".result-card:has(.result-actions > .score) .result-body" in source
    assert "position:relative!important" in source
    assert "top:-6px!important" in source
    assert "padding-top:" not in source
    assert "padding-bottom:" not in source


def test_windows_launcher_injects_content_versioned_polish(tmp_path) -> None:
    ui2 = tmp_path / "app/ui2"
    assets = ui2 / "assets"
    assets.mkdir(parents=True)

    required = [
        "jurisprudence_search.js",
        "search_investigation_bridge.js",
        "windows_live_badge_cleanup.js",
        "windows_search_results_polish.js",
        "app_runtime.js",
    ]
    for name in required:
        (assets / name).write_text("// " + name, encoding="utf-8")
    (ui2 / "navigator_3_3_4a.js").write_text("// navigator", encoding="utf-8")
    (ui2 / "index.html").write_text(
        "<html><head></head><body></body></html>", encoding="utf-8"
    )

    ensure_ui_assets(tmp_path)

    html = (ui2 / "index.html").read_text(encoding="utf-8")
    assert "assets/windows_search_results_polish.js?v=windows-search-results-" in html
