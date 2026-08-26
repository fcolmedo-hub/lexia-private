import math
import re
from collections import defaultdict
from pathlib import Path

from config.settings import SETTINGS
from models.search_result import SearchResult
from search.authority_ranker import LegalAuthorityRanker
from search.fuzzy_matcher import FuzzyLegalMatcher
from search.legal_thesaurus import LegalQueryExpander
from search.query_parser import LegalQueryParser
from search.boolean_query import parse_boolean_query
from search.boolean_document_search import search_boolean_documents
from search.result_diversifier import ResultDiversifier
from search.vector_store import VectorStore
from storage.catalog import DocumentCatalog
from storage.search_feedback_repository import (
    SearchFeedbackRepository,
)
from storage.search_history_repository import (
    SearchHistoryRepository,
)


class ProfessionalLegalSearchEngine:
    def __init__(
        self,
        vector_store: VectorStore,
        catalog: DocumentCatalog,
        feedback: SearchFeedbackRepository,
        history: SearchHistoryRepository,
    ):
        self.vector_store = vector_store
        self.catalog = catalog
        self.feedback = feedback
        self.history = history
        self.expander = LegalQueryExpander()
        self.parser = LegalQueryParser()
        self.authority = LegalAuthorityRanker()
        self.fuzzy = FuzzyLegalMatcher()
        self.diversifier = ResultDiversifier()

    def search(
        self,
        query: str,
        limit: int = 10,
        category: str | None = None,
        expand_query: bool = True,
    ) -> list[SearchResult]:
        parsed = self.parser.parse(query)
        boolean_query = parse_boolean_query(query)

        if boolean_query.explicit:
            rows = search_boolean_documents(
                self.catalog.database_path,
                boolean_query,
                limit=limit,
                category=category,
            )

            final = []

            for rank, row in enumerate(rows, start=1):
                result = SearchResult(
                    document_name=row["document_name"],
                    document_path=Path(
                        row["document_path"]
                    ),
                    category=row["category"],
                    fragment_index=int(
                        row.get("fragment_index", 0)
                    ),
                    text=row["text_content"],
                    score=max(
                        0.01,
                        1.0 - (rank - 1) * 0.01,
                    ),
                    lexical_rank=rank,
                    page_start=row.get("page_start"),
                    page_end=row.get("page_end"),
                )

                result.matched_queries.append(query)
                final.append(result)

            self.history.add(
                query,
                category,
                len(final),
            )

            return final

        variants = (
            [query]
            if boolean_query.explicit
            else self._variants(query, expand_query)
        )
        candidate_limit = min(
            SETTINGS.search_candidates_per_variant,
            max(
                SETTINGS.search_min_candidates,
                limit * 2,
            ),
        )

        scores: dict[tuple[str, int], float] = defaultdict(float)
        results: dict[tuple[str, int], SearchResult] = {}

        for idx, variant in enumerate(variants):
            weight = (
                1.0
                if idx == 0
                else max(
                    0.48,
                    0.70 - idx * 0.10,
                )
            )

            if boolean_query.explicit:
                semantic = []
                lexical_query = boolean_query.fts_query
            else:
                semantic = self.vector_store.search(
                    variant,
                    candidate_limit,
                    category,
                )
                lexical_query = self._fts_query(variant)

            lexical = self.catalog.lexical_search(
                lexical_query,
                candidate_limit,
                category,
            )

            for rank, result in enumerate(
                semantic,
                start=1,
            ):
                key = (
                    str(result.document_path.resolve()),
                    result.fragment_index,
                )
                scores[key] += weight * (
                    0.56 * float(result.score)
                    + 0.44 / (55 + rank)
                )
                results.setdefault(key, result)

                if variant not in results[key].matched_queries:
                    results[key].matched_queries.append(
                        variant
                    )

            for rank, row in enumerate(
                lexical,
                start=1,
            ):
                key = (
                    str(
                        Path(
                            row["document_path"]
                        ).resolve()
                    ),
                    int(row["fragment_index"]),
                )
                scores[key] += weight * (
                    0.52 / (42 + rank)
                )

                if key not in results:
                    results[key] = SearchResult(
                        document_name=row[
                            "document_name"
                        ],
                        document_path=Path(
                            row["document_path"]
                        ),
                        category=row["category"],
                        fragment_index=int(
                            row["fragment_index"]
                        ),
                        text=row["text_content"],
                        score=0.0,
                        lexical_rank=rank,
                        page_start=row.get(
                            "page_start"
                        ),
                        page_end=row.get(
                            "page_end"
                        ),
                    )

                if variant not in results[key].matched_queries:
                    results[key].matched_queries.append(
                        variant
                    )

        feedback_scores = self.feedback.aggregate_scores(
            list(scores.keys())
        )

        for key, result in results.items():
            result.authority_score = (
                self.authority.score(result)
            )
            result.exact_match_score = (
                self._exact_match_score(
                    parsed.original,
                    result,
                )
            )
            (
                result.fuzzy_score,
                result.matched_terms,
            ) = self.fuzzy.score(
                query,
                result.document_name,
                result.text,
            )
            result.feedback_score = (
                feedback_scores.get(key, 0.0)
            )
            authority_bonus = (
                math.log(
                    max(
                        result.authority_score,
                        1.0,
                    ),
                    2,
                )
                * 0.09
            )
            result.score = (
                scores[key]
                + authority_bonus
                + result.exact_match_score
                + result.fuzzy_score
                + result.feedback_score
            )

        ranked = sorted(
            results.values(),
            key=lambda item: item.score,
            reverse=True,
        )
        final = self.diversifier.diversify(
            ranked,
            limit,
        )
        self.history.add(
            query,
            category,
            len(final),
        )
        return final

    def _variants(
        self,
        query: str,
        expand_query: bool,
    ) -> list[str]:
        if not expand_query:
            return [query]

        raw = self.expander.expand(query)
        output = []
        seen = set()

        for value in raw:
            clean = " ".join(str(value).split()).strip()
            key = clean.casefold()

            if clean and key not in seen:
                output.append(clean)
                seen.add(key)

            if (
                len(output)
                >= SETTINGS.search_max_query_variants
            ):
                break

        return output or [query]

    def _exact_match_score(
        self,
        query: str,
        result: SearchResult,
    ) -> float:
        haystack = (
            f"{result.document_name} {result.text}"
            .lower()
        )
        original = query.lower().strip()
        score = (
            0.22
            if original and original in haystack
            else 0.0
        )
        tokens = [
            token
            for token in re.findall(
                r"[A-Za-zÁÉÍÓÚÑáéíóúñ0-9\.]+",
                original,
            )
            if len(token) > 2
        ]

        if tokens:
            score += (
                sum(
                    1
                    for token in tokens
                    if token in haystack
                )
                / len(tokens)
                * 0.12
            )

        return min(score, 0.45)

    def _fts_query(self, query: str) -> str:
        tokens = [
            token
            for token in re.findall(
                r"[A-Za-zÁÉÍÓÚÑáéíóúñ0-9\.]+",
                query,
            )
            if len(token) > 2
        ]
        return (
            " OR ".join(
                f'"{token}"'
                for token in tokens[:10]
            )
            or query
        )
