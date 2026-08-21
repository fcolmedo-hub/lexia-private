import re
from difflib import SequenceMatcher

class FuzzyLegalMatcher:
    def score(self, query: str, document_name: str, text: str) -> tuple[float, list[str]]:
        query_tokens = self._tokens(query)
        haystack_tokens = self._tokens(f"{document_name} {text[:5000]}")
        if not query_tokens or not haystack_tokens:
            return 0.0, []
        matched, scores = [], []
        for token in query_tokens:
            best_token, best_score = "", 0.0
            for candidate in haystack_tokens:
                if abs(len(candidate) - len(token)) > 3:
                    continue
                score = SequenceMatcher(None, token, candidate).ratio()
                if score > best_score:
                    best_token, best_score = candidate, score
            if best_score >= 0.86:
                matched.append(best_token)
                scores.append(best_score)
        if not scores:
            return 0.0, []
        coverage = len(scores) / len(query_tokens)
        return min(0.12, sum(scores) / len(scores) * coverage * 0.12), matched

    def _tokens(self, text: str) -> list[str]:
        return [t.lower() for t in re.findall(r"[A-Za-zÁÉÍÓÚÑáéíóúñ0-9]+", text) if len(t) >= 4]
