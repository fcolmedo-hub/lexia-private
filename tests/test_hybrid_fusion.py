from pathlib import Path

from models.search_result import SearchResult
from search.hybrid_search import HybridSearchEngine


def test_rrf_combines_semantic_and_lexical_results() -> None:
    engine = object.__new__(HybridSearchEngine)

    semantic = [
        SearchResult(
            document_name="fallo.txt",
            document_path=Path("data/fallo.txt"),
            category="Jurisprudencia",
            fragment_index=0,
            text="Responsabilidad estatal.",
            score=0.8,
        )
    ]

    lexical = [
        {
            "document_name": "fallo.txt",
            "document_path": str(Path("data/fallo.txt").resolve()),
            "category": "Jurisprudencia",
            "fragment_index": 0,
            "text_content": "Responsabilidad estatal.",
        }
    ]

    results = engine._reciprocal_rank_fusion(
        semantic,
        lexical,
        limit=10,
    )

    assert len(results) == 1
    assert results[0].semantic_rank == 1
    assert results[0].lexical_rank == 1
    assert results[0].score > 0
