import re
from dataclasses import dataclass, field


@dataclass(slots=True)
class CitationCheck:
    cited_numbers: list[int] = field(default_factory=list)
    invalid_numbers: list[int] = field(default_factory=list)
    has_citations: bool = False
    warning: str | None = None


class CitationVerifier:
    # Acepta [FUENTE 1], (FUENTE 1), Fuente 1 y variantes de mayúsculas.
    PATTERN = re.compile(
        r"(?:\[|\()?\s*FUENTE\s*(?:N[.°º]?\s*)?(\d+)\s*(?:\]|\))?",
        re.IGNORECASE,
    )

    def normalize(self, answer: str) -> str:
        return self.PATTERN.sub(
            lambda match: f"[FUENTE {int(match.group(1))}]",
            answer,
        )

    def verify(self, answer: str, source_count: int) -> CitationCheck:
        normalized = self.normalize(answer)
        cited = sorted(
            {int(number) for number in self.PATTERN.findall(normalized)}
        )
        invalid = [
            number
            for number in cited
            if number < 1 or number > source_count
        ]
        warning = None
        if not cited:
            warning = "La respuesta no contiene citas [FUENTE N]."
        elif invalid:
            warning = (
                "La respuesta contiene referencias a fuentes inexistentes: "
                + ", ".join(map(str, invalid))
            )
        return CitationCheck(cited, invalid, bool(cited), warning)
