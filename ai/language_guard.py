import re
from dataclasses import dataclass


@dataclass(slots=True)
class LanguageCheck:
    is_spanish: bool
    english_score: int
    spanish_score: int = 0
    english_paragraphs: int = 0
    warning: str | None = None


class SpanishLanguageGuard:
    """Detecta respuestas total o parcialmente redactadas en inglés.

    Es deliberadamente estricto para texto visible al usuario. Tolera nombres
    propios, títulos de fallos y términos aislados, pero rechaza párrafos cuya
    sintaxis sea predominantemente inglesa.
    """

    ENGLISH_WORDS = {
        "the", "and", "based", "provided", "sources", "source", "however",
        "therefore", "according", "appears", "cannot", "could", "would",
        "should", "may", "might", "legal", "entity", "evidence", "conclusion",
        "analysis", "lack", "absence", "must", "this", "that", "these", "those",
        "with", "without", "from", "into", "between", "under", "which", "while",
        "where", "when", "because", "although", "apply", "applicable", "requires",
        "required", "request", "rights", "court", "administrative", "act",
    }

    SPANISH_WORDS = {
        "el", "la", "los", "las", "y", "de", "del", "que", "por", "para",
        "con", "sin", "según", "fuentes", "fuente", "conclusión", "análisis",
        "derecho", "jurídico", "jurídica", "prueba", "hechos", "tribunal",
        "corresponde", "permite", "sostener", "administrativo", "acto", "debe",
        "puede", "resulta", "norma", "jurisprudencia", "sin embargo", "además",
    }

    ENGLISH_PHRASES = (
        "based on", "provided sources", "it appears", "please note",
        "in this case", "according to", "legal entity", "lack of",
        "the sources", "cannot be", "should be", "may be considered",
    )

    def check(self, text: str) -> LanguageCheck:
        cleaned = self._without_citations(text)
        words = re.findall(r"[a-záéíóúñü]+", cleaned.lower())
        english_score = sum(word in self.ENGLISH_WORDS for word in words)
        spanish_score = sum(word in self.SPANISH_WORDS for word in words)

        normalized = " " + re.sub(r"\s+", " ", cleaned.lower()) + " "
        english_score += 3 * sum(
            normalized.count(f" {phrase} ") for phrase in self.ENGLISH_PHRASES
        )

        english_paragraphs = 0
        for paragraph in re.split(r"\n\s*\n", cleaned):
            p_words = re.findall(r"[a-záéíóúñü]+", paragraph.lower())
            if len(p_words) < 8:
                continue
            en = sum(word in self.ENGLISH_WORDS for word in p_words)
            es = sum(word in self.SPANISH_WORDS for word in p_words)
            if en >= 4 and en > es * 1.25:
                english_paragraphs += 1

        substantial_english = (
            english_paragraphs > 0
            or english_score >= 8 and english_score > spanish_score
            or english_score >= 14
        )

        warning = None
        if substantial_english:
            warning = (
                "La salida fue rechazada porque contiene texto sustancial "
                "en inglés."
            )

        return LanguageCheck(
            is_spanish=not substantial_english,
            english_score=english_score,
            spanish_score=spanish_score,
            english_paragraphs=english_paragraphs,
            warning=warning,
        )

    def _without_citations(self, text: str) -> str:
        return re.sub(r"\[FUENTE\s+\d+\]", " ", text, flags=re.IGNORECASE)
