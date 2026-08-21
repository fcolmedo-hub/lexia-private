from collections import defaultdict

from config.settings import SETTINGS
from models.query_interpretation import QueryInterpretation
from models.search_result import SearchResult


class InterpretedLegalSearchEngine:
    """
    Ejecuta una cantidad acotada de consultas jurídicas.

    La consulta principal admite expansión profesional. Las consultas
    secundarias ya provienen del intérprete/Knowledge Planner y no se
    expanden nuevamente. Esto evita la multiplicación combinatoria que
    hacía cientos de consultas vectoriales por investigación.
    """

    def __init__(self, search_engine):
        self.search_engine = search_engine

    def search(
        self,
        interpretation: QueryInterpretation,
        limit: int = 10,
    ) -> list[SearchResult]:
        scores: dict[tuple[str, int], float] = defaultdict(float)
        results: dict[tuple[str, int], SearchResult] = {}

        queries = self._queries(interpretation)
        per_query_limit = min(
            max(limit, 12),
            SETTINGS.interpreted_per_query_limit,
        )

        for index, query in enumerate(queries):
            weight = (
                1.0
                if index == 0
                else max(
                    0.42,
                    0.76 - index * 0.08,
                )
            )

            query_results = self.search_engine.search(
                query=query,
                limit=per_query_limit,
                category=None,
                expand_query=(index == 0),
            )

            for rank, result in enumerate(
                query_results,
                start=1,
            ):
                key = (
                    str(result.document_path.resolve()),
                    result.fragment_index,
                )
                scores[key] += weight * (
                    result.score
                    + 1.0 / (40 + rank)
                )
                results.setdefault(key, result)

                if query not in result.matched_queries:
                    result.matched_queries.append(query)

        ordered = sorted(
            results.values(),
            key=lambda item: scores[
                (
                    str(item.document_path.resolve()),
                    item.fragment_index,
                )
            ],
            reverse=True,
        )

        for result in ordered:
            key = (
                str(result.document_path.resolve()),
                result.fragment_index,
            )
            result.score = scores[key]

        return ordered[:limit]

    def _queries(
        self,
        interpretation: QueryInterpretation,
    ) -> list[str]:
        values = (
            interpretation.search_queries
            or [interpretation.original_query]
        )
        output = []
        seen = set()

        for value in values:
            clean = " ".join(str(value).split()).strip()
            key = clean.casefold()

            if clean and key not in seen:
                output.append(clean)
                seen.add(key)

            if len(output) >= SETTINGS.interpreted_max_queries:
                break

        return output or [interpretation.original_query]
