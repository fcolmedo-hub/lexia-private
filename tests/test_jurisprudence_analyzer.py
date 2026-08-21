from ai.jurisprudence_analyzer import JurisprudenceAnalyzer


def test_chunker_preserves_page_range() -> None:
    analyzer = JurisprudenceAnalyzer()
    text = (
        "--- PÁGINA 1 ---\n" + "A" * 3000
        + "\n--- PÁGINA 2 ---\n" + "B" * 3000
        + "\n--- PÁGINA 3 ---\n" + "C" * 3000
    )
    chunks = analyzer._chunk(text)
    assert chunks
    assert chunks[0].page_start == 1
    assert chunks[-1].page_end == 3


def test_plain_text_chunker() -> None:
    analyzer = JurisprudenceAnalyzer()
    chunks = analyzer._chunk(("Párrafo jurídico.\n\n" * 500))
    assert len(chunks) >= 1
