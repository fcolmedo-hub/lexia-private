from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class KnowledgePlan:
    search_queries: tuple[str, ...]
    concepts: tuple[str, ...]
    related_concepts: tuple[str, ...]
    required_categories: tuple[str, ...]
    preferred_authorities: tuple[str, ...]
    jurisdictions: tuple[str, ...]
    missing_dimensions: tuple[str, ...]
    confidence: float

    def to_dict(self):
        return {
            "search_queries": list(self.search_queries), "concepts": list(self.concepts),
            "related_concepts": list(self.related_concepts), "required_categories": list(self.required_categories),
            "preferred_authorities": list(self.preferred_authorities), "jurisdictions": list(self.jurisdictions),
            "missing_dimensions": list(self.missing_dimensions), "confidence": self.confidence,
        }


class DeterministicLegalPlanner:
    def __init__(self, repository, extractor):
        self.repository = repository
        self.extractor = extractor

    def plan(self, query, interpretation=None):
        document = self.extractor.extract("__query__", "", "consulta", "", query)
        interpreted_queries = getattr(interpretation, "search_queries", ()) or ()
        query_values = self._unique((str(query or ""), *interpreted_queries))[:8]
        concepts = document.concepts
        related = self._unique(
            (*getattr(interpretation, "subtopics", ()), *getattr(interpretation, "procedural_issues", ()))
        )[:8]
        categories = tuple(getattr(interpretation, "preferred_categories", ()) or ("Jurisprudencia", "Legislación", "Doctrina"))
        jurisdiction = getattr(interpretation, "jurisdiction", "")
        jurisdictions = () if jurisdiction in (None, "", "No determinada") else (str(jurisdiction),)
        missing = () if concepts else ("Instituto jurídico principal",)
        return KnowledgePlan(
            search_queries=query_values, concepts=concepts, related_concepts=related,
            required_categories=categories, preferred_authorities=document.authorities,
            jurisdictions=jurisdictions or document.jurisdictions, missing_dimensions=missing,
            confidence=0.75 if concepts else 0.45,
        )

    @staticmethod
    def _unique(values):
        return tuple(dict.fromkeys(str(value).strip() for value in values if str(value).strip()))
