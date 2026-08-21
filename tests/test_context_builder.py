from pathlib import Path
from ai.context_builder import LegalContextBuilder
from models.search_result import SearchResult


def test_context_numbers_sources():
    result = SearchResult(
        document_name="fallo.pdf",
        document_path=Path("data/fallo.pdf"),
        category="Jurisprudencia",
        fragment_index=0,
        text="Texto jurídico relevante.",
        score=1.0,
    )
    packets = LegalContextBuilder().build([result])
    assert packets[0].number == 1
    assert "fallo.pdf" in packets[0].label
