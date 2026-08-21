from pathlib import Path


def test_library_windows_tree_2_9_testfix():
    ui = (Path(__file__).parents[1] / "app" / "ui.py").read_text(
        encoding="utf-8-sig"
    )

    assert "library_top_names" in ui
    assert "library_folder_tree_nodes" in ui
    assert "library_folder_labels" in ui
    assert '"lexia_library_folder_tree"' in ui
