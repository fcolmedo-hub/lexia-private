from legal.precedent_extractor import PrecedentExtractor


def test_extracts_precedent_signal() -> None:
    text = (
        "Esta Corte ha sostenido que la responsabilidad estatal "
        "requiere daño cierto y relación causal."
    )
    candidates = PrecedentExtractor().extract(text)
    assert candidates
