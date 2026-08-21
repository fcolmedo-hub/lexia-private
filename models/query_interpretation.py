from dataclasses import dataclass, field


@dataclass(slots=True)
class QueryInterpretation:
    original_query: str
    area: str = "No determinada"
    main_institute: str = "No determinado"
    conduct: list[str] = field(default_factory=list)
    claim_or_goal: str = "No determinada"
    damages: list[str] = field(default_factory=list)
    procedural_issues: list[str] = field(default_factory=list)
    jurisdiction: str = "No determinada"
    subjects: list[str] = field(default_factory=list)
    cited_rules: list[str] = field(default_factory=list)
    subtopics: list[str] = field(default_factory=list)
    preferred_categories: list[str] = field(default_factory=list)
    search_queries: list[str] = field(default_factory=list)
    confidence: float = 0.0
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "original_query": self.original_query,
            "area": self.area,
            "main_institute": self.main_institute,
            "conduct": self.conduct,
            "claim_or_goal": self.claim_or_goal,
            "damages": self.damages,
            "procedural_issues": self.procedural_issues,
            "jurisdiction": self.jurisdiction,
            "subjects": self.subjects,
            "cited_rules": self.cited_rules,
            "subtopics": self.subtopics,
            "preferred_categories": self.preferred_categories,
            "search_queries": self.search_queries,
            "confidence": self.confidence,
            "notes": self.notes,
        }
