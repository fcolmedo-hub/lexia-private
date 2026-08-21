from dataclasses import dataclass

from ai.citation_verifier import CitationCheck, CitationVerifier
from ai.context_builder import LegalContextBuilder, SourcePacket
from ai.language_guard import LanguageCheck, SpanishLanguageGuard
from ai.lm_studio_client import LMStudioClient
from ai.response_guard import SpanishLegalResponseGuard
from models.query_interpretation import QueryInterpretation
from models.search_result import SearchResult


@dataclass(slots=True)
class AIResearchResult:
    answer: str
    interpretation: QueryInterpretation
    sources: list[SourcePacket]
    citation_check: CitationCheck
    language_check: LanguageCheck | None = None


class LegalAIEngine:
    SYSTEM_PROMPT = """SOS LEXIA, ABOGADO ARGENTINO ESPECIALIZADO EN INVESTIGACIÓN JURÍDICA.

REGLAS ABSOLUTAS:
1. RESPONDÉ SIEMPRE Y EXCLUSIVAMENTE EN ESPAÑOL.
2. ESTÁ PROHIBIDO INCLUIR PÁRRAFOS, TÍTULOS, RESÚMENES O TRADUCCIONES EN INGLÉS.
3. NO USES CONOCIMIENTO EXTERNO: TRABAJÁ SOLO CON LAS FUENTES SUMINISTRADAS.
4. NO INVENTES FALLOS, NORMAS, HECHOS, FECHAS, TRIBUNALES NI CITAS.
5. TODA AFIRMACIÓN JURÍDICA RELEVANTE DEBE TERMINAR CON [FUENTE N].
6. SI LAS FUENTES NO RESPONDEN UN PUNTO, ESCRIBÍ: "Las fuentes recuperadas no permiten sostenerlo".
7. DIFERENCIÁ REGLA JURÍDICA, APLICACIÓN AL CASO, INFERENCIA Y RECOMENDACIÓN.
8. NO REPITAS LA RESPUESTA EN DOS IDIOMAS.
9. NO COMIENCES CON FÓRMULAS GENÉRICAS COMO "Based on..." O "Please note...".

ESTRUCTURA OBLIGATORIA:
## Conclusión
## Fundamentos jurídicos
## Aplicación a los hechos
## Objeciones o criterios adversos
## Prueba necesaria
## Limitaciones de las fuentes
"""

    def __init__(self, interpreted_search, interpreter):
        self.interpreted_search = interpreted_search
        self.interpreter = interpreter
        self.client = LMStudioClient()
        self.context_builder = LegalContextBuilder()
        self.verifier = CitationVerifier()
        self.language_guard = SpanishLanguageGuard()
        self.response_guard = SpanishLegalResponseGuard(self.client)

    def research(
        self,
        query: str,
        facts: str = "",
        limit: int = 12,
    ) -> AIResearchResult:
        interpretation = self.interpreter.interpret(query)
        results: list[SearchResult] = self.interpreted_search.search(
            interpretation,
            limit=limit,
        )
        packets = self.context_builder.build(results)
        if not packets:
            raise RuntimeError(
                "LexIA no recuperó fuentes para esta consulta. "
                "Agregá documentos o reformulá la búsqueda."
            )

        user_prompt = f"""CONSULTA JURÍDICA:
{query.strip()}

HECHOS SUMINISTRADOS:
{facts.strip() or '[No se suministraron hechos adicionales]'}

INTERPRETACIÓN PRELIMINAR:
- Área: {interpretation.area}
- Instituto: {interpretation.main_institute}
- Pretensión: {interpretation.claim_or_goal}
- Jurisdicción: {interpretation.jurisdiction}
- Subtemas: {', '.join(interpretation.subtopics) or 'No determinados'}

FUENTES DOCUMENTALES:
{self.context_builder.render(packets)}

INSTRUCCIÓN FINAL:
Respondé directamente en español jurídico argentino y con la estructura obligatoria.
No utilices ninguna información ajena a las fuentes. Cada conclusión debe llevar [FUENTE N].
"""

        raw_answer = self.client.chat(
            self.SYSTEM_PROMPT,
            user_prompt,
            max_tokens=800,
            temperature=0.0,
        )
        guarded = self.response_guard.enforce(
            raw_answer,
            source_count=len(packets),
            original_query=query,
            max_tokens=800,
        )
        answer = guarded.text
        return AIResearchResult(
            answer=answer,
            interpretation=interpretation,
            sources=packets,
            citation_check=self.verifier.verify(answer, len(packets)),
            language_check=self.language_guard.check(answer),
        )
