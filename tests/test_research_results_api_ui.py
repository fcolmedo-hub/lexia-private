from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_bridge_sends_packages_to_openai_and_archives_only_the_answer():
    source = (ROOT / "services" / "ui2_delete_bridge.py").read_text(
        encoding="utf-8"
    )
    assert "ResearchAnswerService().answer" in source
    assert 'kind="research"' in source
    assert 'kind="file"' in source
    assert 'Path(SETTINGS.runtime_path) / "research_results.sqlite3"' in source
    assert 'request_path == "/api/ai-results"' in source
    assert 'request_path.startswith("/api/ai-results/")' in source
    assert 'result_archive.search(query)' in source
    assert 'self.path == "/api/ai-results-delete"' in source
    assert 'result_archive.delete(int(body.get("id")))' in source
    assert '"content": answer.text' in source


def test_shared_ui_hides_package_and_adds_history_and_popup():
    source = (ROOT / "app" / "ui2" / "assets" / "research_results.js").read_text(
        encoding="utf-8"
    )
    assert "#contextpage .output-card{display:none!important}" in source
    assert "packageCard?.remove()" in source
    assert "Últimos resultados" in source
    assert "Investigaciones y estudios guardados" in source
    assert "'/api/ai-results/'" in source
    assert "showResult(data.result||{})" in source
    assert 'placeholder="Buscar por nombre, consulta o contenido"' in source
    assert "window.confirm(" in source
    assert "'/api/ai-results-delete'" in source
    assert "#researchSourcesModal{display:none!important}" in source
    assert "lexia-source-review" in source
    assert "Proceso de IA" in source
    assert "enterSourceReview()" in source
    assert "resetResearchLayout()" in source
    assert "setInterval" not in source
    assert "MutationObserver" not in source


def test_ui2_server_proxies_result_history_to_the_core_bridge():
    source = (ROOT / "app" / "ui2" / "server.py").read_text(
        encoding="utf-8"
    )
    assert 'def _core_ai_results(path="/api/ai-results", query="")' in source
    assert '_delete_bridge_request("GET", clean_path)' in source
    assert 'def _core_ai_result_delete(payload)' in source
    assert '"POST", "/api/ai-results-delete", payload' in source
    assert 'urlencode({"query": str(query).strip()})' in source
    assert 'path == "/api/ai-results" or path.startswith("/api/ai-results/")' in source


def test_both_desktop_launchers_load_shared_results_ui():
    windows = (ROOT / "app" / "ui2" / "windows_desktop.py").read_text(
        encoding="utf-8"
    )
    macos = (ROOT / "app" / "ui2" / "macos_desktop.py").read_text(
        encoding="utf-8"
    )
    assert 'here / "assets" / "research_results.js"' in windows
    assert 'here / "assets" / "research_results.js"' in macos
    assert '"research-results"' in windows
    assert "research-results-" in macos
