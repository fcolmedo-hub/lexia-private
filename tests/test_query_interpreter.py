from legal.query_interpreter import LegalQueryInterpreter


def test_interpreter_detects_state_liability() -> None:
    result = LegalQueryInterpreter().interpret(
        "Indemnización por demora municipal "
        "en habilitar un establecimiento"
    )

    assert result.area == "Derecho administrativo"
    assert result.claim_or_goal == "Indemnización"
    assert "Demora administrativa" in result.conduct
    assert result.search_queries
