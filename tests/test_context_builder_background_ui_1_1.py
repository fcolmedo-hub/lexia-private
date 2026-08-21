from pathlib import Path


def _research_section(ui: str) -> str:
    start = ui.index('    if prepare_mode == "Investigar en la biblioteca":')
    end = ui.index(
        '\n    else:\n        st.caption(\n'
        '            "Subí un PDF, DOC, DOCX o TXT.',
        start,
    )
    return ui[start:end]


def test_context_result_uses_service_as_single_source_of_truth():
    ui = Path("app/ui.py").read_text(encoding="utf-8")
    section = _research_section(ui)

    assert "completed_context_job = app.context_build_jobs.result()" in section
    assert "show_package(completed_context_job.package)" in section
    assert "context_last_loaded_job_id" not in section

    # El resultado del trabajo en segundo plano no debe copiarse a session_state.
    assert "st.session_state.context_package = result.package" not in section
    assert (
        "st.session_state.context_package = completed_context_job.package"
        not in section
    )


def test_completed_fragment_forces_full_page_refresh_once():
    ui = Path("app/ui.py").read_text(encoding="utf-8")
    assert "context_completed_refresh_" in ui
    assert "st.rerun()" in ui
