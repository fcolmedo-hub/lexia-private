from dataclasses import dataclass
from pathlib import Path


@dataclass(slots=True)
class Fragment:
    document_name: str
    document_path: Path
    category: str
    index: int
    text: str
    start_char: int
    end_char: int
    page_start: int | None = None
    page_end: int | None = None

    @property
    def length(self) -> int:
        return len(self.text)

    @property
    def page_label(self) -> str:
        if self.page_start is None:
            return "Página no determinada"

        if self.page_end is None or self.page_end == self.page_start:
            return f"Página {self.page_start}"

        return f"Páginas {self.page_start}-{self.page_end}"
