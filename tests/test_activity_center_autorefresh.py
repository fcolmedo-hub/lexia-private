from pathlib import Path


def test_activity_center_has_live_fragment():
    source = Path("app/ui.py").read_text(encoding="utf-8")

    assert "def _render_activity_center_live():" in source
    assert 'run_every="1s"' in source
    assert "_render_activity_center_live()" in source


def test_manual_sync_button_still_present():
    source = Path("app/ui.py").read_text(encoding="utf-8")

    assert '"Analizar cambios"' in source
    assert "app.autosync.sync_now()" in source

