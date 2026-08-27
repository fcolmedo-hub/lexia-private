from __future__ import annotations

import inspect
import sqlite3
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
from app.ui2.jurisprudence_search import (
    load_filtered_metadata,
    metadata_bonus,
    parse_filter_envelope,
)

try:
    from search.search_hotfix import SearchHotfixEngine
except Exception:
    SearchHotfixEngine = None


class SearchRuntime:
    """LexIA's professional search stack, with optional jurisprudence metadata filters."""

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

    @staticmethod
    def _metadata_only_rows(metadata_map: dict[str, dict], limit: int) -> list[dict]:
        paths = list(metadata_map.keys())[:limit]
        if not paths:
            return []
        con = sqlite3.connect(str(SETTINGS.catalog_path), timeout=15)
        con.row_factory = sqlite3.Row
        try:
            placeholders = ",".join("?" for _ in paths)
            rows = con.execute(
                f"SELECT path,name,category FROM documents WHERE path IN ({placeholders}) AND COALESCE(is_deleted,0)=0",
                paths,
            ).fetchall()
        finally:
            con.close()
        by_path = {str(row["path"]): row for row in rows}
        result = []
        for path in paths:
            row = by_path.get(path)
            if row is None:
                continue
            meta = metadata_map[path]
            preview = meta.get("case_title") or meta.get("court") or meta.get("case_number") or ""
            result.append({
                "rank": len(result) + 1,
                "document_name": str(row["name"] or "Documento"),
                "document_path": path,
                "category": str(row["category"] or "Jurisprudencia"),
                "text": str(preview),
                "score": 50.0,
                "page_start": None,
                "page_end": None,
                "semantic_rank": None,
                "lexical_rank": None,
                "jurisprudence": meta,
                "metadata_bonus": 0.0,
            })
        return result

    def search(self, query: str, limit: int = 20, category: str | None = None) -> dict:
        original_query = str(query or "").strip()
        clean_query, juris_filters = parse_filter_envelope(original_query)

        category = str(category or "").strip() or None
        if category in {"Todos", "Todas"}:
            category = None
        is_juris = bool(category and category.casefold() == "jurisprudencia")
        if juris_filters and not is_juris:
            juris_filters = {}

        requested_limit = max(1, int(limit or 20))
        # Filtros estructurados necesitan una reserva mayor de candidatos antes
        # de aplicar el recorte final, sin alterar el motor base FTS/Qdrant.
        engine_limit = min(max(requested_limit * (8 if juris_filters else 1), 120 if juris_filters else requested_limit), 400)

        metadata_map: dict[str, dict] = {}
        if is_juris:
            metadata_map = load_filtered_metadata(
                SETTINGS.catalog_path,
                juris_filters,
            )

        if not clean_query:
            if not (is_juris and juris_filters):
                raise ValueError("La consulta está vacía.")
            results = self._metadata_only_rows(metadata_map, requested_limit)
            return {
                "ok": True,
                "query": "",
                "category": category,
                "count": len(results),
                "elapsed_seconds": 0.0,
                "results": results,
                "engine": "LexIA Professional Search + Jurisprudence Index",
                "jurisprudence_filters": juris_filters,
            }

        started = time.perf_counter()
        raw = self._call_search(self.search_engine, clean_query, engine_limit, category)
        elapsed = time.perf_counter() - started

        if isinstance(raw, dict):
            rows = raw.get("results") or raw.get("items") or []
        elif hasattr(raw, "results"):
            rows = getattr(raw, "results")
        else:
            rows = raw or []

        converted = [
            self._result_dict(item, i)
            for i, item in enumerate(list(rows)[:engine_limit], start=1)
        ]

        enriched = []
        for item in converted:
            path = str(item.get("document_path") or "")
            if is_juris:
                meta = metadata_map.get(path)
                if juris_filters and meta is None:
                    continue
                if meta is None:
                    # Sin filtros seguimos pudiendo enriquecer resultados que
                    # existan en el índice completo.
                    full = load_filtered_metadata(SETTINGS.catalog_path, {})
                    meta = full.get(path)
                if meta:
                    bonus = metadata_bonus(meta, clean_query)
                    item["jurisprudence"] = meta
                    item["metadata_bonus"] = round(bonus, 1)
                    item["score"] = round(min(100.0, float(item.get("score", 0.0)) + bonus), 1)
            enriched.append(item)

        enriched.sort(key=lambda row: float(row.get("score", 0.0)), reverse=True)
        results = enriched[:requested_limit]
        for idx, item in enumerate(results, start=1):
            item["rank"] = idx

        return {
            "ok": True,
            "query": clean_query,
            "category": category,
            "count": len(results),
            "elapsed_seconds": round(elapsed, 2),
            "results": results,
            "engine": "LexIA Professional Search + Jurisprudence Index" if is_juris else "LexIA Professional Search",
            "jurisprudence_filters": juris_filters,
        }
