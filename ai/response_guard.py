from dataclasses import dataclass

from ai.citation_verifier import CitationVerifier
from ai.language_guard import SpanishLanguageGuard
from ai.lm_studio_client import LMStudioClient


@dataclass(slots=True)
class GuardResult:
    text: str
    repaired: bool
    valid_spanish: bool
    valid_citations: bool


class SpanishLegalResponseGuard:
    """Valida y repara toda salida visible del modelo.

    Nunca devuelve al usuario una respuesta sustancialmente escrita en inglés.
    """

    REPAIR_SYSTEM = """SOS LEXIA, ABOGADO ARGENTINO REVISOR.

REGLAS ABSOLUTAS E INNEGOCIABLES:
1. ESCRIBÍ TODA LA RESPUESTA EXCLUSIVAMENTE EN ESPAÑOL.
2. NO INCLUYAS NINGUNA TRADUCCIÓN, PÁRRAFO, TÍTULO NI CONCLUSIÓN EN INGLÉS.
3. CONSERVÁ SOLAMENTE INFORMACIÓN CONTENIDA EN EL TEXTO A CORREGIR.
4. NO AGREGUES JURISPRUDENCIA, NORMAS, HECHOS NI CONOCIMIENTO EXTERNO.
5. USÁ LAS CITAS ÚNICAMENTE CON EL FORMATO EXACTO [FUENTE N].
6. NO CITES FUENTES QUE NO ESTÉN EN LA LISTA DE FUENTES VÁLIDAS.
7. SI NO EXISTE RESPALDO, ESCRIBÍ: "Las fuentes recuperadas no permiten sostenerlo".
8. ENTREGÁ DIRECTAMENTE LA VERSIÓN CORREGIDA, SIN EXPLICAR LA CORRECCIÓN.
"""

    def __init__(self, client: LMStudioClient | None = None):
        self.client = client or LMStudioClient()
        self.language = SpanishLanguageGuard()
        self.citations = CitationVerifier()

    def enforce(
        self,
        answer: str,
        source_count: int,
        original_query: str,
        max_tokens: int = 850,
    ) -> GuardResult:
        current = self.citations.normalize(answer)

        for attempt in range(3):
            language_check = self.language.check(current)
            citation_check = self.citations.verify(current, source_count)
            citation_valid = (
                citation_check.has_citations
                and not citation_check.invalid_numbers
            )

            if language_check.is_spanish and citation_valid:
                return GuardResult(
                    text=current,
                    repaired=attempt > 0,
                    valid_spanish=True,
                    valid_citations=True,
                )

            valid_sources = ", ".join(
                f"[FUENTE {number}]"
                for number in range(1, source_count + 1)
            )
            current = self.client.chat(
                self.REPAIR_SYSTEM,
                self._repair_prompt(
                    current,
                    original_query,
                    valid_sources,
                    attempt,
                ),
                max_tokens=max_tokens,
                temperature=0.0,
            )
            current = self.citations.normalize(current)

        final_language = self.language.check(current)
        final_citations = self.citations.verify(current, source_count)
        if not final_language.is_spanish:
            # Nunca se muestra al usuario la salida inglesa defectuosa.
            current = (
                "## Resultado no disponible\n\n"
                "Mistral no respetó el requisito obligatorio de responder "
                "exclusivamente en español. LexIA descartó la respuesta para "
                "evitar mostrar un análisis defectuoso. Reintentá la consulta."
            )
            return GuardResult(current, True, False, False)

        return GuardResult(
            text=current,
            repaired=True,
            valid_spanish=True,
            valid_citations=(
                final_citations.has_citations
                and not final_citations.invalid_numbers
            ),
        )

    def ensure_spanish_only(
        self,
        text: str,
        max_tokens: int = 450,
    ) -> str:
        if self.language.check(text).is_spanish:
            return self.citations.normalize(text)

        current = text
        for _ in range(3):
            current = self.client.chat(
                self.REPAIR_SYSTEM,
                """REESCRIBÍ EL SIGUIENTE TEXTO ÍNTEGRAMENTE EN ESPAÑOL JURÍDICO.
No agregues ni elimines conclusiones. Conservá exactamente las citas [FUENTE N].
No incluyas el texto original ni una traducción paralela.

TEXTO:
""" + current,
                max_tokens=max_tokens,
                temperature=0.0,
            )
            current = self.citations.normalize(current)
            if self.language.check(current).is_spanish:
                return current

        return (
            "LexIA descartó un análisis parcial porque Mistral no respetó "
            "el idioma español."
        )

    def _repair_prompt(
        self,
        answer: str,
        query: str,
        valid_sources: str,
        attempt: int,
    ) -> str:
        return f"""CONSULTA ORIGINAL:
{query}

FUENTES VÁLIDAS:
{valid_sources}

RESPUESTA A REVISAR:
{answer}

TAREA DE REVISIÓN — INTENTO {attempt + 1}:
- Reescribí íntegramente la respuesta en español jurídico argentino.
- Eliminá todo texto en inglés, incluso títulos y advertencias.
- No repitas primero el inglés y luego el español.
- Conservá solo citas válidas y normalizalas como [FUENTE N].
- Eliminá afirmaciones sin respaldo o marcá insuficiencia documental.
- No agregues información nueva.
- Entregá directamente la respuesta final.
"""
