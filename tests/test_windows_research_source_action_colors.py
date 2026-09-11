from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_windows_research_source_actions_have_semantic_colors() -> None:
    source = (
        ROOT / "app/ui2/assets/windows_search_results_polish.js"
    ).read_text(encoding="utf-8")

    assert ".source-actions .study-source" in source
    assert "background:#5146f6!important" in source
    assert ".source-actions .lexia-case-link" in source
    assert "background:#8a5a2b!important" in source


def test_ocr_action_is_hidden_from_research_sources() -> None:
    source = (
        ROOT / "app/ui2/assets/windows_search_results_polish.js"
    ).read_text(encoding="utf-8")

    marker = ".source-actions .lexia-ocr-reprocess"
    assert marker in source
    block = source.split(marker, 1)[1].split("}", 1)[0]
    assert "display:none!important" in block
    assert "background:#e87514!important" not in block


def test_color_override_remains_windows_only() -> None:
    windows = (ROOT / "app/ui2/windows_desktop.py").read_text(encoding="utf-8")
    macos = (ROOT / "app/ui2/macos_desktop.py").read_text(encoding="utf-8")

    assert "windows_search_results_polish.js" in windows
    assert "windows_search_results_polish.js" not in macos
