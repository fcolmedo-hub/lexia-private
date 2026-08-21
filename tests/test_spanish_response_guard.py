from ai.language_guard import SpanishLanguageGuard


def test_rejects_english_paragraph():
    text = (
        "Based on the provided sources, the administrative act may be "
        "considered invalid because it lacks a legal basis and motivation."
    )
    assert SpanishLanguageGuard().check(text).is_spanish is False


def test_rejects_bilingual_response():
    text = (
        "Based on the provided sources, the act may be invalid.\n\n"
        "De las fuentes surge que el acto podría ser ilegítimo."
    )
    assert SpanishLanguageGuard().check(text).is_spanish is False


def test_accepts_spanish_legal_response():
    text = (
        "## Conclusión\n\nEl acto administrativo puede presentar un "
        "vicio en la competencia [FUENTE 1]."
    )
    assert SpanishLanguageGuard().check(text).is_spanish is True
