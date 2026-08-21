import re
from dataclasses import dataclass, field


@dataclass(slots=True)
class ParsedQuery:
    original: str
    quoted_phrases: list[str] = field(default_factory=list)
    legal_citations: list[str] = field(default_factory=list)
    named_entities: list[str] = field(default_factory=list)


class LegalQueryParser:
    def parse(self, query: str) -> ParsedQuery:
        quoted = re.findall(r'"([^"]+)"', query)

        citations = re.findall(
            r"\b(?:ley|decreto|resolución|art(?:ículo)?\.?)\s+"
            r"[\d\.\-/]+",
            query,
            flags=re.IGNORECASE,
        )

        named = re.findall(
            r"\b[A-ZÁÉÍÓÚÑ][A-Za-zÁÉÍÓÚÑáéíóúñ]+"
            r"(?:\s+[A-ZÁÉÍÓÚÑ][A-Za-zÁÉÍÓÚÑáéíóúñ]+){0,4}",
            query,
        )

        return ParsedQuery(
            original=query,
            quoted_phrases=quoted,
            legal_citations=citations,
            named_entities=named,
        )
