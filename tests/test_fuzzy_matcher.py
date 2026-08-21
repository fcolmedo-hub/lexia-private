from search.fuzzy_matcher import FuzzyLegalMatcher

def test_fuzzy_matcher_handles_typo() -> None:
    score, terms = FuzzyLegalMatcher().score(
        "responzabilidad estatal",
        "fallo.pdf",
        "Responsabilidad estatal por falta de servicio.",
    )
    assert score > 0
    assert "responsabilidad" in terms
