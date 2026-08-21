import hashlib
import json
from pathlib import Path

from models.search_result import SearchResult
from storage.search_cache_repository import (
    SearchCacheRepository,
)


class CachedSearchEngine:
    def __init__(
        self,
        engine,
        cache: SearchCacheRepository,
    ):
        self.engine = engine
        self.cache = cache
        self.last_cache_hit = False

    def search(
        self,
        query: str,
        limit: int = 10,
        category: str | None = None,
        expand_query: bool = True,
    ) -> list[SearchResult]:
        cache_key = self._key(
            query,
            limit,
            category,
            expand_query,
        )
        cached = self.cache.get(cache_key)

        if cached is not None:
            self.last_cache_hit = True
            return [
                SearchResult(
                    document_name=item["document_name"],
                    document_path=Path(item["document_path"]),
                    category=item["category"],
                    fragment_index=item["fragment_index"],
                    text=item["text"],
                    score=item["score"],
                    semantic_rank=item.get("semantic_rank"),
                    lexical_rank=item.get("lexical_rank"),
                    page_start=item.get("page_start"),
                    page_end=item.get("page_end"),
                    authority_score=item.get("authority_score", 1.0),
                    exact_match_score=item.get("exact_match_score", 0.0),
                    metadata_score=item.get("metadata_score", 0.0),
                    feedback_score=item.get("feedback_score", 0.0),
                    fuzzy_score=item.get("fuzzy_score", 0.0),
                    matched_queries=item.get("matched_queries", []),
                    matched_terms=item.get("matched_terms", []),
                    metadata=item.get("metadata", {}),
                )
                for item in cached
            ]

        self.last_cache_hit = False
        results = self.engine.search(
            query=query,
            limit=limit,
            category=category,
            expand_query=expand_query,
        )

        self.cache.set(
            cache_key,
            [
                {
                    "document_name": item.document_name,
                    "document_path": str(item.document_path),
                    "category": item.category,
                    "fragment_index": item.fragment_index,
                    "text": item.text,
                    "score": item.score,
                    "semantic_rank": item.semantic_rank,
                    "lexical_rank": item.lexical_rank,
                    "page_start": item.page_start,
                    "page_end": item.page_end,
                    "authority_score": item.authority_score,
                    "exact_match_score": item.exact_match_score,
                    "metadata_score": item.metadata_score,
                    "feedback_score": item.feedback_score,
                    "fuzzy_score": item.fuzzy_score,
                    "matched_queries": item.matched_queries,
                    "matched_terms": item.matched_terms,
                    "metadata": item.metadata,
                }
                for item in results
            ],
        )

        return results

    def _key(
        self,
        query: str,
        limit: int,
        category: str | None,
        expand_query: bool,
    ) -> str:
        payload = json.dumps(
            {
                "query": query.strip().lower(),
                "limit": limit,
                "category": category,
                "expand_query": expand_query,
            },
            ensure_ascii=False,
            sort_keys=True,
        )

        return hashlib.sha256(
            payload.encode("utf-8")
        ).hexdigest()
