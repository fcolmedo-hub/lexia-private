from pathlib import Path

from models.search_result import SearchResult
from search.result_diversifier import ResultDiversifier


def test_limits_results_per_document() -> None:
    results = [
        SearchResult(
            document_name="libro.pdf",
            document_path=Path("data/Doctrina/libro.pdf"),
            category="Doctrina",
            fragment_index=index,
            text=f"Texto distinto {index} " + ("a " * 100),
            score=1.0 - index * 0.01,
        )
        for index in range(5)
    ]

    diversified = ResultDiversifier().diversify(
        results,
        limit=10,
    )

    assert len(diversified) <= 2
