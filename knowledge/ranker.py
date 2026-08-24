from __future__ import annotations

from knowledge.extractor import DeterministicKnowledgeExtractor


class DeterministicKnowledgeRanker:
    """Reordena resultados existentes; nunca reemplaza la búsqueda semántica."""

    def __init__(self, repository):
        self.repository = repository
        self.extractor = DeterministicKnowledgeExtractor()

    def rank(self, results, plan, limit):
        ranked = []
        for position, result in enumerate(results or (), start=1):
            text = " ".join((str(getattr(result, "document_name", "")), str(getattr(result, "text", ""))))
            knowledge = self.extractor.extract(
                str(getattr(result, "document_path", "")), "", str(getattr(result, "document_name", "")),
                str(getattr(result, "category", "")), text,
            )
            expected = {item.casefold() for item in getattr(plan, "concepts", ())}
            matched = tuple(item for item in knowledge.concepts if item.casefold() in expected)
            authority = knowledge.authorities[0] if knowledge.authorities else ""
            base = float(getattr(result, "score", 0.0) or 0.0)
            score = base + len(matched) * 0.12
            ranked.append((score, result, list(matched), authority, position))
        ranked.sort(key=lambda item: (-item[0], item[4]))
        return [item[:4] for item in ranked[: max(0, int(limit))]]
