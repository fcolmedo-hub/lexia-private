from pathlib import Path


def test_library_windows_tree_2_9():
    root = Path(__file__).parents[1]
    ui = (root / "app" / "ui.py").read_text(encoding="utf-8-sig")
    component = root / "app" / "components" / "lexia_folder_tree"
    index = component / "index.html"
    javascript = component / "assets" / "index.js"

    assert '_LIBRARY_FOLDER_TREE_COMPONENT = components.declare_component(' in ui
    assert '"lexia_library_folder_tree"' in ui
    assert 'def _library_folder_tree(' in ui
    assert "library_children_by_parent" in ui
    assert "def _build_library_folder_nodes(" in ui
    assert 'key="library_folder_tree_selection"' in ui
    assert "library_folder_tree_nodes" in ui

    start = ui.index('st.markdown("#### Carpetas")')
    end = ui.index("include_library_subfolders", start)
    assert "st.multiselect(" not in ui[start:end]
    assert "_library_folder_tree(" in ui[start:end]

    assert index.is_file()
    assert javascript.is_file()
    assert "./assets/index.js" in index.read_text(encoding="utf-8")
    bundle = javascript.read_text(encoding="utf-8")
    assert "setComponentValue" in bundle
    assert len(bundle) > 1000
