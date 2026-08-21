from pathlib import Path


def test_library_folder_cache_and_notice_2_8():
    ui = (Path(__file__).parents[1] / "app" / "ui.py").read_text(
        encoding="utf-8-sig"
    )

    assert 'library_folder_cache_version = "2.8"' in ui
    assert 'or not st.session_state.get("_library_folder_counts_cache")' in ui
    assert 'st.session_state._library_folder_cache_version' in ui
    assert 'app.catalog.folder_counts()' in ui

    assert "deletion_finished_at" in ui
    assert "deletion_state_is_recent" in ui
    assert "time.time() - deletion_finished_at <= 30" in ui
    assert (
        'deletion_state.get("status") == "completed"\n'
        "        and deletion_state_is_recent"
    ) in ui
