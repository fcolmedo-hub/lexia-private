from collections import defaultdict

from config.settings import SETTINGS
from models.search_result import SearchResult


class ResultDiversifier:
    def diversify(
        self,
        results: list[SearchResult],
        limit: int,
    ) -> list[SearchResult]:
        selected: list[SearchResult] = []
        per_document: dict[str, int] = defaultdict(int)

        for result in results:
            document_key = str(result.document_path.resolve())

            if (
                per_document[document_key]
                >= SETTINGS.max_results_per_document
            ):
                continue

            if self._too_similar(result, selected):
                continue

            selected.append(result)
            per_document[document_key] += 1

            if len(selected) >= limit:
                break

        return selected

    def _too_similar(
        self,
        candidate: SearchResult,
        selected: list[SearchResult],
    ) -> bool:
        candidate_tokens = set(candidate.text.lower().split())

        for existing in selected:
            if candidate.document_path != existing.document_path:
                continue

            existing_tokens = set(existing.text.lower().split())

            if not candidate_tokens or not existing_tokens:
                continue

            intersection = len(candidate_tokens & existing_tokens)
            union = len(candidate_tokens | existing_tokens)

            if union and intersection / union > 0.78:
                return True

        return False
