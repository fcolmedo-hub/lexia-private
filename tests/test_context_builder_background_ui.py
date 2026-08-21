from pathlib import Path


def _research_section(ui: str) -> str:
    start = ui.index('    if prepare_mode == "Investigar en la biblioteca":')
    end = ui.index(
        '\n    else:\n        st.caption(\n'
        '            "Subí un PDF, DOC, DOCX o TXT.',
        start,
    )
    return ui[start:end]


def test_context_builder_uses_background_service():
    ui = Path("app/ui.py").read_text(encoding="utf-8")
    app = Path("services/application.py").read_text(encoding="utf-8")
    section = _research_section(ui)

    assert "app.context_build_jobs.start_job(" in section
    assert "build_research_package(" not in section
    assert "ContextBuildService" in app
    assert "def context_build_jobs" in app
