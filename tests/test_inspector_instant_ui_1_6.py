from pathlib import Path


def test_inspector_instant_ui():
    ui = (
        Path(__file__).parents[1] / "app" / "ui.py"
    ).read_text(encoding="utf-8")

    catalog = (
        Path(__file__).parents[1] / "storage" / "catalog.py"
    ).read_text(encoding="utf-8")

    assert 'with st.form("inspector_filters_form")' in ui
    assert "form_submit_button" in ui
    assert '"Aplicar filtros"' in ui
    assert "st.session_state.inspector_matches" in ui
    assert "limit=None" in ui
    assert 'Path(row["path"]).parent.resolve()' not in catalog
    assert "limit: int | None = None" in catalog