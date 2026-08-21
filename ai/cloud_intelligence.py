from dataclasses import dataclass
from pathlib import Path

from ai.openai_client import OpenAIAnswer, OpenAIClient
from config.settings import SETTINGS
from core.document_extractor import DocumentExtractor
from models.search_result import SearchResult


@dataclass(slots=True)
class CloudResearchResult:
    answer: str
    sources: list[SearchResult]
    input_tokens: int
    output_tokens: int
    total_tokens: int
    response_id: str


class CloudIntelligence:
    SYSTEM_INSTRUCTIONS = """
Sos LexIA, un asistente jurídico para un abogado argentino.

REGLAS OBLIGATORIAS:
- Respondé exclusivamente en español.
- Trabajá únicamente con la consulta, los hechos y las fuentes suministradas.
- No inventes fallos, normas, citas, fechas, tribunales ni hechos.
- Toda afirmación jurídica sustancial debe incluir una referencia exacta
  con el formato [FUENTE N].
- Si las fuentes son insuficientes, decilo expresamente.
- Separá claramente: contenido de las fuentes, inferencias y recomendaciones.
- Priorizá precisión jurídica y utilidad procesal.
- Señalá criterios adversos, riesgos, prueba faltante y limitaciones.
- No menciones que sos un modelo de lenguaje.
"""

    DOCUMENT_INSTRUCTIONS = """
Sos LexIA, un asistente jurídico para un abogado argentino.

Analizá exclusivamente el documento suministrado. Respondé en español.
No inventes datos ausentes. Cuando el texto sea incompleto, indicá la
limitación.

Estructura:
1. Resumen ejecutivo.
2. Identificación del documento.
3. Hechos y antecedentes.
4. Problema jurídico.
5. Argumentos de las partes.
6. Fundamentos decisivos.
7. Decisión.
8. Regla o doctrina jurídica extraíble.
9. Utilidad práctica.
10. Limitaciones, votos o disidencias.
11. Explicación sencilla.
"""

    def __init__(
        self,
        interpreted_search,
        query_interpreter,
    ):
        self.search = interpreted_search
        self.interpreter = query_interpreter
        self.client = OpenAIClient()
        self.extractor = DocumentExtractor()

    def research(
        self,
        query: str,
        facts: str = "",
        limit: int | None = None,
    ) -> CloudResearchResult:
        interpretation = self.interpreter.interpret(query)
        results = self.search.search(
            interpretation,
            limit=limit or SETTINGS.cloud_max_sources,
        )
        results = results[: SETTINGS.cloud_max_sources]

        if not results:
            raise RuntimeError(
                "LexIA no encontró fuentes para esta consulta."
            )

        context = self._render_sources(results)
        user_input = f"""
CONSULTA JURÍDICA:
{query.strip()}

HECHOS SUMINISTRADOS:
{facts.strip() or "[No se suministraron hechos adicionales]"}

INTERPRETACIÓN PRELIMINAR:
Área: {interpretation.area}
Instituto: {interpretation.main_institute}
Pretensión: {interpretation.claim_or_goal}
Jurisdicción: {interpretation.jurisdiction}
Subtemas: {", ".join(interpretation.subtopics) or "No determinados"}

FUENTES RECUPERADAS POR LEXIA:
{context}

TAREA:
Elaborá una respuesta jurídica profesional, trazable y útil para litigación.
Incluí: conclusión, fundamentos favorables, criterios adversos, prueba
necesaria, riesgos procesales, estrategia sugerida e información faltante.
"""

        answer = self.client.respond(
            self.SYSTEM_INSTRUCTIONS,
            user_input,
        )

        return CloudResearchResult(
            answer=answer.text,
            sources=results,
            input_tokens=answer.input_tokens,
            output_tokens=answer.output_tokens,
            total_tokens=answer.total_tokens,
            response_id=answer.response_id,
        )

    def analyze_uploaded(
        self,
        path: str | Path,
        instruction: str = "",
    ) -> OpenAIAnswer:
        extraction = self.extractor.extract(path)
        text = extraction.text.strip()

        if not text:
            raise RuntimeError(
                "No fue posible extraer texto del documento."
            )

        text = text[: SETTINGS.uploaded_document_max_chars]

        user_input = f"""
DOCUMENTO:
Nombre: {Path(path).name}
Método de extracción: {extraction.method}
Páginas detectadas: {extraction.total_pages or "No determinadas"}

INDICACIÓN ADICIONAL DEL USUARIO:
{instruction.strip() or "[Ninguna]"}

TEXTO:
{text}
"""

        return self.client.respond(
            self.DOCUMENT_INSTRUCTIONS,
            user_input,
            max_output_tokens=SETTINGS.openai_max_output_tokens,
        )

    def _render_sources(
        self,
        results: list[SearchResult],
    ) -> str:
        blocks: list[str] = []
        used_chars = 0

        for number, result in enumerate(results, start=1):
            metadata = result.metadata or {}
            text = " ".join(result.text.split())
            text = text[: SETTINGS.cloud_max_chars_per_source]

            block = (
                f"[FUENTE {number}]\n"
                f"Documento: {result.document_name}\n"
                f"Categoría: {result.category}\n"
                f"Ubicación: {result.page_label}\n"
                f"Tribunal: {metadata.get('court', 'No detectado')}\n"
                f"Fecha: {metadata.get('date', 'No detectada')}\n"
                f"Ruta local: {result.document_path}\n"
                f"Contenido: {text}"
            )

            if (
                blocks
                and used_chars + len(block)
                > SETTINGS.cloud_max_context_chars
            ):
                break

            blocks.append(block)
            used_chars += len(block)

        return "\n\n".join(blocks)
