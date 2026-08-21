import re

from models.document import Document
from models.fragment import Fragment


PAGE_PATTERN = re.compile(r"--- PÁGINA (\d+) ---")


class DocumentChunker:
    def __init__(self, chunk_size: int = 1800, overlap: int = 250):
        if chunk_size <= 0:
            raise ValueError("chunk_size debe ser mayor que cero.")
        if overlap < 0 or overlap >= chunk_size:
            raise ValueError(
                "overlap debe ser mayor o igual a cero y menor que chunk_size."
            )

        self.chunk_size = chunk_size
        self.overlap = overlap

    def split(self, document: Document) -> list[Fragment]:
        text = self._normalize(document.text)

        if not text:
            return []

        page_marks = self._page_marks(text)
        fragments: list[Fragment] = []
        start = 0
        index = 0

        while start < len(text):
            tentative_end = min(start + self.chunk_size, len(text))
            end = self._natural_break(text, start, tentative_end)
            fragment_text = text[start:end].strip()

            if fragment_text:
                page_start = self._page_at(page_marks, start)
                page_end = self._page_at(page_marks, max(start, end - 1))

                fragments.append(
                    Fragment(
                        document_name=document.name,
                        document_path=document.path,
                        category=document.category,
                        index=index,
                        text=fragment_text,
                        start_char=start,
                        end_char=end,
                        page_start=page_start,
                        page_end=page_end,
                    )
                )
                index += 1

            if end >= len(text):
                break

            start = max(end - self.overlap, start + 1)

        return fragments

    def _page_marks(self, text: str) -> list[tuple[int, int]]:
        return [
            (match.start(), int(match.group(1)))
            for match in PAGE_PATTERN.finditer(text)
        ]

    def _page_at(
        self,
        page_marks: list[tuple[int, int]],
        position: int,
    ) -> int | None:
        page = None

        for mark_position, mark_page in page_marks:
            if mark_position > position:
                break
            page = mark_page

        return page

    def _natural_break(
        self,
        text: str,
        start: int,
        tentative_end: int,
    ) -> int:
        if tentative_end >= len(text):
            return len(text)

        search_start = start + int(self.chunk_size * 0.6)
        region = text[search_start:tentative_end]

        paragraph_break = region.rfind("\n\n")
        if paragraph_break != -1:
            return search_start + paragraph_break + 2

        best_sentence_break = max(
            region.rfind(mark)
            for mark in (". ", "? ", "! ", "; ", ": ")
        )
        if best_sentence_break != -1:
            return search_start + best_sentence_break + 1

        whitespace_break = region.rfind(" ")
        if whitespace_break != -1:
            return search_start + whitespace_break

        return tentative_end

    def _normalize(self, text: str) -> str:
        text = text.replace("\r\n", "\n").replace("\r", "\n")
        text = re.sub(r"[\t ]+", " ", text)
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip()
