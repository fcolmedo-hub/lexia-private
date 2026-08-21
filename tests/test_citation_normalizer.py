from ai.citation_verifier import CitationVerifier


def test_normalizes_parenthesized_citations() -> None:
    verifier = CitationVerifier()
    text = "La regla surge de (FUENTE 1) y Fuente 2."
    normalized = verifier.normalize(text)
    assert "[FUENTE 1]" in normalized
    assert "[FUENTE 2]" in normalized
    check = verifier.verify(normalized, 2)
    assert check.cited_numbers == [1, 2]
