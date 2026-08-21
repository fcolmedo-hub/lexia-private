from __future__ import annotations

import inspect
import time
from pathlib import Path
from typing import Any

from config.settings import SETTINGS
from search.embedding_service import EmbeddingService
from search.vector_store import VectorStore
from search.professional_search import ProfessionalLegalSearchEngine
from search.cached_search import CachedSearchEngine
from storage.catalog import DocumentCatalog
from storage.search_feedback_repository import SearchFeedbackRepository
from storage.search_history_repository import SearchHistoryRepository
from storage.search_cache_repository import SearchCacheRepository

try:
    from search.search_hotfix import SearchHotfixEngine
except Exception:
    SearchHotfixEngine = None


class SearchRuntime:
    """LexIA's real professional search stack, without LexIAApplication/AutoSync."""

    def __init__(self) -> None:
        self.catalog = DocumentCatalog(SETTINGS.catalog_path)
        self.feedback = SearchFeedbackRepository(SETTINGS.feedback_path)
        self.history = SearchHistoryRepository(
            SETTINGS.runtime_path / "search_history.sqlite3"
        )
        self.cache = SearchCacheRepository(SETTINGS.search_cache_path)
        self.embeddings = EmbeddingService()
        self.vector_store = VectorStore(self.embeddings)

        professional = ProfessionalLegalSearchEngine(
            self.vector_store,
            self.catalog,
            self.feedback,
            self.history,
        )
        self.raw_search = (
            SearchHotfixEngine(professional, self.catalog)
            if SearchHotfixEngine is not None
            else professional
        )
        self.search_engine = CachedSearchEngine(self.raw_search, self.cache)

    @staticmethod
    def _call_search(engine, query: str, limit: int, category: str | None):
        fn = engine.search
        sig = inspect.signature(fn)
        kwargs = {}
        if "query" in sig.parameters:
            kwargs["query"] = query
        if "limit" in sig.parameters:
            kwargs["limit"] = limit
        if "category" in sig.parameters and category:
            kwargs["category"] = category

        if kwargs:
            try:
                return fn(**kwargs)
            except TypeError:
                pass

        # Compatibility fallbacks for older stable signatures.
        if category:
            try:
                return fn(query, limit, category)
            except TypeError:
                pass
        try:
            return fn(query, limit)
        except TypeError:
            return fn(query)

    @staticmethod
    def _result_dict(item: Any, rank: int) -> dict:
        def get(*names, default=None):
            for name in names:
                if isinstance(item, dict) and name in item:
                    return item[name]
                if hasattr(item, name):
                    return getattr(item, name)
            return default

        score = get("score", "final_score", "relevance", default=0.0)
        try:
            score = float(score or 0.0)
        except Exception:
            score = 0.0

        # Most search scores are 0..1; tolerate already-percent-like values.
        score_pct = score * 100.0 if score <= 1.5 else score
        score_pct = max(0.0, min(100.0, score_pct))

        path = get("document_path", "path", default="")
        return {
            "rank": rank,
            "document_name": str(get("document_name", "name", "title", default="Documento")),
            "document_path": str(path or ""),
            "category": str(get("category", default="") or ""),
            "text": str(get("text", "snippet", "content", default="") or ""),
            "score": round(score_pct, 1),
            "page_start": get("page_start", default=None),
            "page_end": get("page_end", default=None),
            "semantic_rank": get("semantic_rank", default=None),
            "lexical_rank": get("lexical_rank", default=None),
        }

    def search(self, query: str, limit: int = 20, category: str | None = None) -> dict:
        query = str(query or "").strip()
        if not query:
            raise ValueError("La consulta está vacía.")

        limit = max(1, min(int(limit or 20), 50))
        category = str(category or "").strip() or None
        if category in {"Todos", "Todas"}:
            category = None

        started = time.perf_counter()
        raw = self._call_search(self.search_engine, query, limit, category)
        elapsed = time.perf_counter() - started

        # Search engines may return a list/tuple or an envelope.
        if isinstance(raw, dict):
            rows = raw.get("results") or raw.get("items") or []
        elif hasattr(raw, "results"):
            rows = getattr(raw, "results")
        else:
            rows = raw or []

        results = [
            self._result_dict(item, i)
            for i, item in enumerate(list(rows)[:limit], start=1)
        ]

        return {
            "ok": True,
            "query": query,
            "category": category,
            "count": len(results),
            "elapsed_seconds": round(elapsed, 2),
            "results": results,
            "engine": "LexIA Professional Search",
        }
