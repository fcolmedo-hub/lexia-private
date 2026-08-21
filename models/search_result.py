from dataclasses import dataclass, field
from pathlib import Path

@dataclass(slots=True)
class SearchResult:
    document_name: str
    document_path: Path
    category: str
    fragment_index: int
    text: str
    score: float
    semantic_rank: int | None = None
    lexical_rank: int | None = None
    page_start: int | None = None
    page_end: int | None = None
    authority_score: float = 1.0
    exact_match_score: float = 0.0
    metadata_score: float = 0.0
    feedback_score: float = 0.0
    fuzzy_score: float = 0.0
    matched_queries: list[str] = field(default_factory=list)
    matched_terms: list[str] = field(default_factory=list)
    metadata: dict[str, str] = field(default_factory=dict)

    @property
    def page_label(self) -> str:
        if self.page_start is None:
            return "Página no determinada"
        if self.page_end is None or self.page_end == self.page_start:
            return f"Página {self.page_start}"
        return f"Páginas {self.page_start}-{self.page_end}"

    def citation_label(self) -> str:
        return f"{self.document_name} — {self.page_label} — fragmento {self.fragment_index} ({self.category})"
