from ai.citation_verifier import CitationVerifier


def test_valid_citations():
    check = CitationVerifier().verify("Regla [FUENTE 1] y excepción [FUENTE 2].", 2)
    assert check.has_citations
    assert not check.invalid_numbers


def test_invalid_citation():
    check = CitationVerifier().verify("Texto [FUENTE 4].", 2)
    assert check.invalid_numbers == [4]
