from pathlib import Path

from legal.argument_builder import ArgumentBuilder
from models.search_result import SearchResult


def test_builder_uses_selected_sources() -> None:
    source = SearchResult(
        document_name="fallo.pdf",
        document_path=Path("data/Jurisprudencia/fallo.pdf"),
        category="Jurisprudencia",
        fragment_index=1,
        text="La demora administrativa fue ilegítima.",
        score=0.03,
    )

    draft = ArgumentBuilder().build(
        "La actividad estatal fue ilegítima",
        "Existió demora prolongada.",
        [source],
    )

    assert "fallo.pdf" in draft.content
    assert "Existió demora prolongada" in draft.content
