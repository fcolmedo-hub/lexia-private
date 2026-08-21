from pathlib import Path


def test_inspector_uses_multiselect_folder_tree():
    ui = (Path(__file__).parents[1] / "app" / "ui.py").read_text(
        encoding="utf-8"
    )
    assert 'st.markdown("#### Carpetas")' in ui
    assert 'with st.expander(f"📁 {top_name} ({top_total:,})")' in ui
    assert 'selected_folders: list[str] = []' in ui
    assert '"Seleccionar todas"' in ui
    assert '"Limpiar selección"' in ui
