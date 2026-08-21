from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from config.settings import SETTINGS
from core.document_extractor import DocumentExtractor
from models.search_result import SearchResult


@dataclass(slots=True)
class PromptPackage:
    title: str
    prompt: str
    sources: list[SearchResult]
    created_at: str
    character_count: int


class PromptBridge:
    BASE_RULES = """
Actuá como abogado argentino litigante y analista jurídico.
Respondé exclusivamente en español.
Trabajá únicamente con la consulta, los hechos y las fuentes suministradas.
No inventes fallos, normas, citas, fechas, tribunales ni hechos.
Toda afirmación jurídica relevante debe citarse con el formato [FUENTE N].
Si las fuentes no permiten responder, indicá expresamente la insuficiencia.
Diferenciá claramente: contenido de las fuentes, inferencias y recomendaciones.
Identificá criterios favorables y adversos, riesgos procesales y prueba faltante.
No repitas innecesariamente el texto de las fuentes.
""".strip()

    def __init__(self, interpreted_search, query_interpreter):
        self.search = interpreted_search
        self.interpreter = query_interpreter
        self.extractor = DocumentExtractor()

    def build_research_prompt(
        self,
        query: str,
        facts: str = "",
        objective: str = "Investigación jurídica integral",
        max_sources: int | None = None,
    ) -> PromptPackage:
        interpretation = self.interpreter.interpret(query)
        limit = max_sources or SETTINGS.prompt_bridge_max_sources
        results = self.search.search(interpretation, limit=limit)
        results = results[:limit]

        if not results:
            raise RuntimeError(
                "LexIA no encontró fuentes para preparar el contexto."
            )

        sources_text = self._render_sources(results)
        prompt = f"""# PAQUETE DE INVESTIGACIÓN JURÍDICA — LEXIA

## REGLAS OBLIGATORIAS

{self.BASE_RULES}

## OBJETIVO

{objective.strip() or 'Investigación jurídica integral'}

## CONSULTA

{query.strip()}

## HECHOS SUMINISTRADOS

{facts.strip() or '[No se suministraron hechos adicionales]'}

## INTERPRETACIÓN PRELIMINAR DE LEXIA

- Área: {interpretation.area}
- Instituto principal: {interpretation.main_institute}
- Pretensión u objetivo: {interpretation.claim_or_goal}
- Jurisdicción: {interpretation.jurisdiction}
- Conducta: {', '.join(interpretation.conduct) or 'No determinada'}
- Daños: {', '.join(interpretation.damages) or 'No determinados'}
- Cuestiones procesales: {', '.join(interpretation.procedural_issues) or 'No determinadas'}
- Subtemas: {', '.join(interpretation.subtopics) or 'No determinados'}

## TAREA

Elaborá una respuesta jurídica profesional con esta estructura:

1. Conclusión preliminar.
2. Encuadre jurídico.
3. Fundamentos favorables.
4. Criterios adversos o contraargumentos.
5. Aplicación a los hechos suministrados.
6. Prueba necesaria y prueba faltante.
7. Riesgos procesales.
8. Estrategia sugerida.
9. Fuentes decisivas.
10. Información que falta para responder con mayor certeza.

## FUENTES SELECCIONADAS POR LEXIA

{sources_text}

## CONTROL FINAL

Antes de responder, verificá que cada afirmación jurídica relevante tenga una cita [FUENTE N]. No utilices fuentes externas ni conocimiento no contenido en este paquete, salvo que lo identifiques expresamente como conocimiento general y el usuario lo haya pedido.
"""
        return PromptPackage(
            title=self._safe_title(query),
            prompt=prompt,
            sources=results,
            created_at=datetime.now().isoformat(timespec='seconds'),
            character_count=len(prompt),
        )

    def build_document_prompt(
        self,
        path: str | Path,
        instruction: str = "",
        document_type: str = "Detección automática",
    ) -> PromptPackage:
        extraction = self.extractor.extract(path)
        text = extraction.text.strip()
        if not text:
            raise RuntimeError("No fue posible extraer texto del documento.")
        text = text[:SETTINGS.prompt_bridge_upload_max_chars]
        prompt = f"""# PAQUETE DE ANÁLISIS DOCUMENTAL — LEXIA

## REGLAS OBLIGATORIAS

{self.BASE_RULES}

## DOCUMENTO

- Nombre: {Path(path).name}
- Tipo indicado: {document_type}
- Método de extracción: {extraction.method}
- Páginas detectadas: {extraction.total_pages or 'No determinadas'}

## INDICACIÓN DEL USUARIO

{instruction.strip() or 'Analizá integralmente el documento.'}

## TAREA

Detectá el tipo de documento y elaborá, según corresponda:

1. Resumen ejecutivo.
2. Identificación del documento y su finalidad.
3. Hechos y antecedentes.
4. Pretensión, agravios o cuestión jurídica.
5. Argumentos centrales.
6. Normas, jurisprudencia y doctrina citadas.
7. Decisión o petición.
8. Fortalezas.
9. Debilidades, contradicciones y omisiones.
10. Prueba disponible y prueba faltante.
11. Utilidad práctica.
12. Explicación sencilla.

En un fallo, distinguí ratio decidendi, obiter dicta, votos y disidencias. En un escrito, evaluá coherencia entre hechos, derecho, prueba y petitorio.

## TEXTO DEL DOCUMENTO

[FUENTE 1 — DOCUMENTO COMPLETO O EXTRACTO]
{text}
"""
        return PromptPackage(
            title=f"Análisis de {Path(path).stem}",
            prompt=prompt,
            sources=[],
            created_at=datetime.now().isoformat(timespec='seconds'),
            character_count=len(prompt),
        )

def save(self, package: PromptPackage):

    from ai.chatgpt_message_builder import ChatGPTMessageBuilder
    import json

    SETTINGS.prompt_exports_path.mkdir(
        parents=True,
        exist_ok=True,
    )

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    folder = (
        SETTINGS.prompt_exports_path
        / f"{stamp}_{package.title}"
    )

    folder.mkdir(exist_ok=True)

    context_path = folder / "Contexto.txt"

    context_path.write_text(
        package.prompt,
        encoding="utf-8",
    )

    message = ChatGPTMessageBuilder().build()

    message_path = folder / "Mensaje_ChatGPT.txt"

    message_path.write_text(
        message,
        encoding="utf-8",
    )

    metadata = {
        "title": package.title,
        "created_at": package.created_at,
        "characters": package.character_count,
        "sources": len(package.sources),
    }

    (folder / "metadata.json").write_text(
        json.dumps(
            metadata,
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    return folder
    def _render_sources(self, results: list[SearchResult]) -> str:
        blocks = []
        total = 0
        for number, result in enumerate(results, start=1):
            metadata = result.metadata or {}
            text = ' '.join(result.text.split())[:SETTINGS.prompt_bridge_max_chars_per_source]
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
            if blocks and total + len(block) > SETTINGS.prompt_bridge_max_total_chars:
                break
            blocks.append(block)
            total += len(block)
        return '\n\n'.join(blocks)

    def _safe_title(self, query: str) -> str:
        clean = ''.join(c if c.isalnum() or c in (' ', '-', '_') else '' for c in query)
        clean = '_'.join(clean.split())[:70]
        return clean or 'consulta_lexia'
