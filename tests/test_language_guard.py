from ai.language_guard import SpanishLanguageGuard


def test_detects_substantial_english_answer() -> None:
    text = (
        "Based on the provided sources, it appears that the legal entity "
        "cannot obtain the benefit. However, the sources are incomplete."
    )
    assert not SpanishLanguageGuard().check(text).is_spanish


def test_accepts_spanish_answer() -> None:
    text = (
        "Las fuentes recuperadas no permiten sostener la conclusión. "
        "Sin embargo, corresponde revisar la jurisprudencia."
    )
    assert SpanishLanguageGuard().check(text).is_spanish
