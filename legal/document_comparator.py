import re
from dataclasses import dataclass, field


@dataclass(slots=True)
class DocumentComparison:
    summary: str
    common_terms: list[str] = field(default_factory=list)
    unique_to_first: list[str] = field(default_factory=list)
    unique_to_second: list[str] = field(default_factory=list)
    common_citations: list[str] = field(default_factory=list)
    first_only_citations: list[str] = field(default_factory=list)
    second_only_citations: list[str] = field(default_factory=list)
    structural_differences: list[str] = field(default_factory=list)


class DocumentComparator:
    LEGAL_STOPWORDS = {
        "para", "como", "este", "esta", "entre", "sobre",
        "desde", "hasta", "también", "porque", "cuando",
        "donde", "cual", "toda", "todo", "todos", "todas",
        "debe", "puede", "parte", "hechos", "derecho",
    }

    SECTION_NAMES = (
        "objeto",
        "hechos",
        "derecho",
        "prueba",
        "petitorio",
        "competencia",
        "reserva del caso federal",
    )

    def compare(
        self,
        first_text: str,
        second_text: str,
    ) -> DocumentComparison:
        first_terms = self._significant_terms(first_text)
        second_terms = self._significant_terms(second_text)

        first_citations = self._citations(first_text)
        second_citations = self._citations(second_text)

        first_sections = self._sections(first_text)
        second_sections = self._sections(second_text)

        structural = []

        for section in self.SECTION_NAMES:
            in_first = section in first_sections
            in_second = section in second_sections

            if in_first != in_second:
                structural.append(
                    f"La sección '{section}' aparece "
                    f"solo en {'el primer documento' if in_first else 'el segundo documento'}."
                )

        common_terms = sorted(
            first_terms & second_terms
        )[:40]
        unique_first = sorted(
            first_terms - second_terms
        )[:40]
        unique_second = sorted(
            second_terms - first_terms
        )[:40]

        common_citations = sorted(
            first_citations & second_citations
        )

        summary = (
            f"Documento 1: {len(first_text)} caracteres. "
            f"Documento 2: {len(second_text)} caracteres. "
            f"Términos jurídicos comunes: {len(common_terms)}. "
            f"Citas comunes: {len(common_citations)}."
        )

        return DocumentComparison(
            summary=summary,
            common_terms=common_terms,
            unique_to_first=unique_first,
            unique_to_second=unique_second,
            common_citations=common_citations,
            first_only_citations=sorted(
                first_citations - second_citations
            ),
            second_only_citations=sorted(
                second_citations - first_citations
            ),
            structural_differences=structural,
        )

    def _significant_terms(self, text: str) -> set[str]:
        tokens = {
            token.lower()
            for token in re.findall(
                r"[A-Za-zÁÉÍÓÚÑáéíóúñ]{5,}",
                text,
            )
        }

        return {
            token
            for token in tokens
            if token not in self.LEGAL_STOPWORDS
        }

    def _citations(self, text: str) -> set[str]:
        patterns = (
            r"\bFallos\s+\d+:\d+\b",
            (
                r"\b(?:Ley|Decreto|Resolución|Ordenanza)\s+"
                r"(?:N[.°º]?\s*)?[\d.\-/]+"
            ),
            (
                r"\bart(?:ículo)?\.?\s*"
                r"\d+(?:\s*(?:bis|ter))?"
            ),
        )

        citations: set[str] = set()

        for pattern in patterns:
            citations.update(
                " ".join(match.group(0).strip().split())
                for match in re.finditer(
                    pattern,
                    text,
                    flags=re.IGNORECASE,
                )
            )

        return citations

    def _sections(self, text: str) -> set[str]:
        lower = text.lower()

        return {
            section
            for section in self.SECTION_NAMES
            if section in lower
        }
