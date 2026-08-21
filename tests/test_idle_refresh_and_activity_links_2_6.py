from pathlib import Path


def test_idle_refresh_and_activity_links_2_6():
    ui = (
        Path(__file__).parents[1] / "app" / "ui.py"
    ).read_text(encoding="utf-8")

    assert "key_suffix=None" in ui
    assert 'key_suffix=f"activity_recent_{item_index}"' in ui
    assert 'key_suffix=f"activity_error_{item_index}"' in ui
    assert 'key_suffix="activity_sync_current"' in ui
    assert "sidebar_busy" in ui
    assert "activity_busy" in ui
    assert "library_live_busy" in ui
    assert "ocr_live_state.get(\"running\")" in ui
    assert "context_fragment is not None and context_job_running" in ui
    assert '"Actualizar estado"' in ui
    assert 'scope="fragment"' not in ui

