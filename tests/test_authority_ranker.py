from pathlib import Path

from models.search_result import SearchResult
from search.authority_ranker import LegalAuthorityRanker


def test_csjn_has_higher_authority() -> None:
    ranker = LegalAuthorityRanker()

    csjn = SearchResult(
        document_name="CSJN fallo.pdf",
        document_path=Path("data/Jurisprudencia/CSJN fallo.pdf"),
        category="Jurisprudencia",
        fragment_index=0,
        text="Corte Suprema de Justicia de la Nación",
        score=0,
    )

    lower = SearchResult(
        document_name="juzgado.pdf",
        document_path=Path("data/Jurisprudencia/juzgado.pdf"),
        category="Jurisprudencia",
        fragment_index=0,
        text="Juzgado de primera instancia",
        score=0,
    )

    assert ranker.score(csjn) > ranker.score(lower)
