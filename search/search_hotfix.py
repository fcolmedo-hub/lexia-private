from __future__ import annotations

import inspect
import json
from pathlib import Path

from models.search_result import SearchResult


class SearchHotfixEngine:
    def __init__(self, wrapped, catalog):
        self.wrapped = wrapped
        self.catalog = catalog

    def __getattr__(self, name):
        return getattr(self.wrapped, name)

    def search(self, query: str, *args, **kwargs):
        clean = str(query or "").strip()
        if not clean:
            return self.wrapped.search(query, *args, **kwargs)

        limit = self._resolve_limit(args, kwargs)
        category = kwargs.get("category")

        expanded_args, expanded_kwargs = self._expanded_call(
            args, kwargs, max(limit * 4, 40)
        )
        base_results = self.wrapped.search(
            query, *expanded_args, **expanded_kwargs
        )

        direct_rows = self.catalog.direct_document_search(
            clean,
            limit=min(max(limit, 10), 50),
            category=category,
        )
        lexical_rows = self.catalog.lexical_search(
            clean,
            limit=min(max(limit * 3, 30), 150),
            category=category,
        )

        direct_results = [
            self._row_to_result(
                row,
                score=2.0 - (index * 0.01),
                source="filename",
                rank=index + 1,
            )
            for index, row in enumerate(direct_rows)
        ]
        lexical_results = [
            self._row_to_result(
                row,
                score=1.20 - min(index, 99) * 0.005,
                source="lexical",
                rank=index + 1,
            )
            for index, row in enumerate(lexical_rows)
        ]

        return self._fuse(
            direct_results,
            lexical_results,
            list(base_results or []),
            limit,
        )

    @staticmethod
    def _resolve_limit(args, kwargs) -> int:
        if "limit" in kwargs:
            try:
                return max(1, int(kwargs["limit"]))
            except Exception:
                pass
        if args:
            try:
                return max(1, int(args[0]))
            except Exception:
                pass
        return 20

    @staticmethod
    def _expanded_call(args, kwargs, expanded_limit):
        args = list(args)
        kwargs = dict(kwargs)
        if "limit" in kwargs:
            kwargs["limit"] = expanded_limit
        elif args:
            try:
                int(args[0])
                args[0] = expanded_limit
            except Exception:
                pass
        return tuple(args), kwargs

    def _row_to_result(self, row, score, source, rank):
        accepted = set(inspect.signature(SearchResult).parameters)

        metadata = row.get("metadata")
        if metadata is None:
            try:
                metadata = json.loads(
                    row.get("metadata_json") or "{}"
                )
            except Exception:
                metadata = {}

        values = {
            "document_name": str(
                row.get("document_name")
                or row.get("name")
                or ""
            ),
            "document_path": Path(
                str(
                    row.get("document_path")
                    or row.get("path")
                    or ""
                )
            ),
            "category": str(row.get("category") or ""),
            "fragment_index": int(
                row.get("fragment_index") or 0
            ),
            "text": str(
                row.get("text_content")
                or row.get("text")
                or ""
            ),
            "score": float(score),
            "semantic_rank": None,
            "lexical_rank": rank if source == "lexical" else None,
            "page_start": row.get("page_start"),
            "page_end": row.get("page_end"),
            "metadata": metadata,
        }

        result = SearchResult(
            **{
                key: value
                for key, value in values.items()
                if key in accepted
            }
        )

        for key, value in (
            ("retrieval_source", source),
            ("direct_match", source == "filename"),
        ):
            try:
                setattr(result, key, value)
            except Exception:
                pass

        return result

    @staticmethod
    def _key(result):
        return (
            str(result.document_path).casefold(),
            int(getattr(result, "fragment_index", 0) or 0),
        )

    def _fuse(self, direct, lexical, semantic, limit):
        merged = {}
        priorities = {}

        for results, source_priority in (
            (direct, 3),
            (lexical, 2),
            (semantic, 1),
        ):
            for result in results:
                key = self._key(result)
                current = merged.get(key)

                if current is None:
                    merged[key] = result
                    priorities[key] = source_priority
                    continue

                new_score = float(
                    getattr(result, "score", 0.0) or 0.0
                )
                old_score = float(
                    getattr(current, "score", 0.0) or 0.0
                )

                if (
                    source_priority > priorities[key]
                    or (
                        source_priority == priorities[key]
                        and new_score > old_score
                    )
                ):
                    merged[key] = result
                    priorities[key] = source_priority

        ordered = list(merged.values())
        ordered.sort(
            key=lambda result: (
                -priorities[self._key(result)],
                -float(getattr(result, "score", 0.0) or 0.0),
                str(result.document_path).casefold(),
                int(getattr(result, "fragment_index", 0) or 0),
            )
        )
        return ordered[:limit]
