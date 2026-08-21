from dataclasses import dataclass, field
from pathlib import Path

from models.fragment import Fragment


@dataclass(slots=True)
class Document:
    name: str
    path: Path
    category: str = "Sin clasificar"
    extension: str = ""
    size: int = 0
    modified_ns: int = 0
    content_hash: str = ""
    text: str = ""
    fragments: list[Fragment] = field(default_factory=list)
    extraction_error: str | None = None
    metadata: dict = field(default_factory=dict)

    extraction_method: str = "native"
    ocr_pages: int = 0
    total_pages: int | None = None
    duplicate_of: str | None = None

    # Index Engine 3.0
    physical_folder: str = ""
    classification_confidence: float = 0.0
    classification_reasons: list[str] = field(default_factory=list)

    @property
    def has_text(self) -> bool:
        return bool(self.text.strip())

    @property
    def fragment_count(self) -> int:
        return len(self.fragments)

    @property
    def is_duplicate(self) -> bool:
        return self.duplicate_of is not None
