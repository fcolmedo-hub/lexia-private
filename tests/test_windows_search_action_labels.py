from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ASSET = ROOT / "app" / "ui2" / "assets" / "windows_search_results_polish.js"


def test_search_action_is_renamed_to_estudiar_without_observer():
    text = ASSET.read_text(encoding="utf-8")
    assert "study.textContent = 'Estudiar'" in text
    assert "study.title = 'Cargar este archivo en Estudiar'" in text
    assert "lexia-result-menu-trigger" in text
    assert "MutationObserver" not in text
    assert "setInterval" not in text


def test_navigator_delete_action_is_white_on_red():
    text = ASSET.read_text(encoding="utf-8")
    assert "#lexiaNavigatorFiles .search-delete-file" in text
    assert ".lexia-nav-preview-actions .search-delete-file" in text
    assert "background:#d92d20!important" in text
    assert "color:#fff!important" in text
