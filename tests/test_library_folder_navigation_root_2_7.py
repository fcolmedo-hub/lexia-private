from pathlib import Path


def test_library_folder_navigation_uses_configured_root():
    ui = (
        Path(__file__).parents[1] / "app" / "ui.py"
    ).read_text(encoding="utf-8")

    start = ui.index("allowed_library_categories")
    end = ui.index("def _clear_library_filters", start)
    folder_block = ui[start:end]

    assert "library_root = _configured_local_path(SETTINGS.library_path)" in folder_block
    assert "relative = folder.relative_to(library_root)" in folder_block
    assert "library_visible_folders" in folder_block
    assert "library_folder_labels" in folder_block
    assert "os.path.commonpath(library_folder_paths)" not in folder_block

