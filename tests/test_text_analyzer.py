from legal.text_analyzer import LegalWritingAnalyzer


def test_analyzer_detects_sections_and_omissions() -> None:
    result = LegalWritingAnalyzer().analyze(
        "OBJETO. Promuevo demanda. HECHOS. Hubo incumplimiento. "
        "DERECHO. Fundo en la ley aplicable."
    )

    assert "objeto" in result["sections"]
    assert any("petitorio" in item.lower() for item in result["omissions"])
