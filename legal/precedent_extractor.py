import re
from dataclasses import dataclass, field


@dataclass(slots=True)
class PrecedentCandidate:
    proposition: str
    source_excerpt: str
    signal: str
    confidence: float


class PrecedentExtractor:
    SIGNALS = (
        "esta corte ha sostenido",
        "se ha dicho",
        "corresponde concluir",
        "cabe señalar",
        "el tribunal resolvió",
        "la doctrina establece",
        "resulta procedente",
        "no resulta procedente",
        "debe interpretarse",
        "no puede sostenerse",
    )

    def extract(self, text: str) -> list[PrecedentCandidate]:
        paragraphs = [
            paragraph.strip()
            for paragraph in re.split(r"\n\s*\n", text)
            if paragraph.strip()
        ]

        candidates: list[PrecedentCandidate] = []

        for paragraph in paragraphs:
            lower = paragraph.lower()

            for signal in self.SIGNALS:
                if signal in lower:
                    proposition = self._clean(paragraph)
                    confidence = min(
                        0.95,
                        0.55 + 0.05 * len(
                            re.findall(
                                r"\b(ley|artículo|fallos|tribunal|corte)\b",
                                lower,
                            )
                        ),
                    )
                    candidates.append(
                        PrecedentCandidate(
                            proposition=proposition[:600],
                            source_excerpt=paragraph[:1200],
                            signal=signal,
                            confidence=round(confidence, 2),
                        )
                    )
                    break

        return candidates[:20]

    def _clean(self, paragraph: str) -> str:
        paragraph = re.sub(r"\s+", " ", paragraph)
        return paragraph.strip()
