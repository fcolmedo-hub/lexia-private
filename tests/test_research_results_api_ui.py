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
    assert '#contextpage:not(.lexia-source-review) #researchPanel>.context-side{display:none!important}' in source
    assert '#contextpage.lexia-source-review #researchPanel>.context-side{order:1!important' in source
    assert '#contextpage.lexia-source-review #researchPanel>#aiProcessCard{order:2!important' in source
    assert "panel.appendChild(card)" in source
    assert "window.lexiaEnterResearchSourceReview=enterSourceReview" in source
    assert "footer.insertBefore(addManual,actions||null)" in source
    assert "#lexiaAddManualResearchSource:hover{background:#17864f!important" in source
    assert "flex:0 0 210px!important" in source
    assert "width:210px!important" in source
    assert "height:36px!important" in source
    assert "#lexiaCaseReturnSelectedSources" in source
    assert "font-size:11px!important" in source
    assert "font-weight:800!important" in source
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


def test_macos_launcher_loads_openai_key_from_keychain_before_services():
    source = (ROOT / "app" / "ui2" / "macos_desktop.py").read_text(
        encoding="utf-8"
    )
    call = "    load_openai_key_from_keychain()"
    services = '    services_log = open(logs / "services_ui2.log"'
    assert 'OPENAI_KEYCHAIN_SERVICE = "LexIA OpenAI API"' in source
    assert '"find-generic-password"' in source
    assert '"-a", account, "-s", OPENAI_KEYCHAIN_SERVICE' in source
    assert 'os.environ["OPENAI_API_KEY"] = key' in source
    assert source.index(call) < source.index(services)


def test_macos_visual_parity_colors_search_actions_and_standards_card():
    source = (
        ROOT / "app" / "ui2" / "assets" / "macos_desktop_parity.js"
    ).read_text(encoding="utf-8")
    assert "const palette = {" in source
    assert "details: ['#f0edff', '#dfd9ff', '#4036b4']" in source
    assert ".lexia-result-menu-trigger" in source
    assert ".lexia-result-menu button" in source
    assert '[role="menu"] button' in source
    assert "[data-lexia-standards-home]:hover" in source
    assert "kind === 'case' || kind === 'ocr'" in source
    assert "forcedActionIcons" in source
    assert "ocr: ['#ece9ff', '#ddd6ff', '#4b3fbd']" in source
    assert "button.dataset.lexiaActionPalette = kind" in source
    assert 'data-lexia-action-palette="case"' in source
    assert 'data-lexia-action-palette="ocr"' in source
    assert "forceLavenderActionIcon" in source
    assert "button.replaceChildren(icon, text)" in source
    assert "lexia-forced-action-icon" in source
    assert "polishHomeRecents" in source
    assert "Consultas recientes de Investigación" in source
    assert "Documentos recientes" in source
    assert "lexia-home-recent-scroll" in source
    assert "recentIcons" in source
    assert "MutationObserver" not in source
    assert "setInterval(" not in source


def test_macos_openai_key_configurator_uses_keychain_without_echoing_key():
    source = (
        ROOT / "scripts" / "configure_openai_key_macos.sh"
    ).read_text(encoding="utf-8")
    assert 'read -rs "openai_key?' in source
    assert "security add-generic-password" in source
    assert 'service_name="LexIA OpenAI API"' in source
    assert "find-generic-password" in source
    assert "https://api.openai.com/v1/models/" in source
    assert "--config -" in source
    assert "Conexión correcta. OPENAI_API_KEY actualizada" in source
