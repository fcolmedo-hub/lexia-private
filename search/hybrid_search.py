from collections import defaultdict
from pathlib import Path

from config.settings import SETTINGS
from models.search_result import SearchResult
from search.vector_store import VectorStore
from storage.catalog import DocumentCatalog


class HybridSearchEngine:
    def __init__(
        self,
        vector_store: VectorStore,
        catalog: DocumentCatalog,
    ):
        self.vector_store = vector_store
        self.catalog = catalog

    def search(
        self,
        query: str,
        limit: int = SETTINGS.default_limit,
        category: str | None = None,
    ) -> list[SearchResult]:
        semantic = self.vector_store.search(
            query=query,
            limit=max(SETTINGS.semantic_candidates, limit * 3),
            category=category,
        )

        lexical = self.catalog.lexical_search(
            query=query,
            limit=max(SETTINGS.lexical_candidates, limit * 3),
            category=category,
        )

        return self._reciprocal_rank_fusion(
            semantic,
            lexical,
            limit,
        )

    def _reciprocal_rank_fusion(
        self,
        semantic: list[SearchResult],
        lexical_rows: list[dict],
        limit: int,
        k: int = 60,
    ) -> list[SearchResult]:
        scores: dict[tuple[str, int], float] = defaultdict(float)
        results: dict[tuple[str, int], SearchResult] = {}

        for rank, result in enumerate(semantic, start=1):
            key = (
                str(result.document_path.resolve()),
                result.fragment_index,
            )
            scores[key] += 1.0 / (k + rank)
            result.semantic_rank = rank
            results[key] = result

        for rank, row in enumerate(lexical_rows, start=1):
            key = (
                str(Path(row["document_path"]).resolve()),
                int(row["fragment_index"]),
            )
            scores[key] += 1.0 / (k + rank)

            if key not in results:
                results[key] = SearchResult(
                    document_name=row["document_name"],
                    document_path=Path(row["document_path"]),
                    category=row["category"],
                    fragment_index=int(row["fragment_index"]),
                    text=row["text_content"],
                    score=0.0,
                    lexical_rank=rank,
                    page_start=row.get("page_start"),
                    page_end=row.get("page_end"),
                )
            else:
                results[key].lexical_rank = rank

        ordered = sorted(
            scores,
            key=scores.get,
            reverse=True,
        )[:limit]

        final: list[SearchResult] = []

        for key in ordered:
            result = results[key]
            result.score = scores[key]
            final.append(result)

        return final
