from search.legal_thesaurus import LegalQueryExpander


def test_expands_state_liability() -> None:
    variants = LegalQueryExpander().expand(
        "responsabilidad del Estado"
    )

    assert "responsabilidad estatal" in variants
    assert "falta de servicio" in variants
