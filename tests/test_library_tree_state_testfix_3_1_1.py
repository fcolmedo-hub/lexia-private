from pathlib import Path


def test_library_tree_state_survives_file_open_rerun():
    ui = (Path(__file__).parents[1] / "app" / "ui.py").read_text(
        encoding="utf-8-sig"
    )

    assert 'stored_tree_selection = st.session_state.get(' in ui
    assert '"library_folder_tree_selection"\n                ) or []' in ui
    assert 'key="library_folder_tree_component"' in ui
    assert "if component_tree_selection is None" in ui
    assert "st.session_state.library_folder_tree_selection = list(" in ui
    assert "if value is None:" in ui
    assert "return None" in ui
