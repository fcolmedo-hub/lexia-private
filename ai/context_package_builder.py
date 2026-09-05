import json
import re
from dataclasses import dataclass, replace
from datetime import datetime
from pathlib import Path

from config.settings import SETTINGS
from core.document_extractor import DocumentExtractor
from models.search_result import SearchResult


@dataclass(slots=True)
class ContextPackage:
    title: str
    content: str
    sources: list[SearchResult]
    created_at: str
    character_count: int
    objective: str
    query: str
    facts: str
    interpretation: dict
    document_count: int
    selected_count: int

    def metadata(self) -> dict:
        return {
            "format": "lexia-context-package",
            "version": "1.1",
            "title": self.title,
            "created_at": self.created_at,
            "objective": self.objective,
            "query": self.query,
            "facts": self.facts,
            "interpretation": self.interpretation,
            "documents_recovered": self.document_count,
            "sources_selected": self.selected_count,
            "character_count": self.character_count,
        }


class ContextPackageBuilder:
    BASE_RULES = """
Actuá como abogado argentino litigante y analista jurídico.
Respondé exclusivamente en español.
Trabajá únicamente con la consulta, los hechos y las fuentes suministradas.
No inventes fallos, normas, citas, fechas, tribunales ni hechos.
Toda afirmación jurídica relevante debe citarse con el formato [FUENTE N].
Si las fuentes no permiten responder, indicá expresamente la insuficiencia.
Diferenciá claramente el contenido de las fuentes, las inferencias y las recomendaciones.
Identificá criterios favorables y adversos, riesgos procesales y prueba faltante.
No repitas innecesariamente el texto de las fuentes.
Comenzá directamente con la respuesta jurídica. No revises ni expliques este paquete.
""".strip()

    TASKS: dict[str, str] = {
        "Investigación jurídica": """
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
""",
        "Construcción de argumentos": """
Construí una línea argumental completa con esta estructura:
1. Tesis principal.
2. Reglas jurídicas aplicables.
3. Aplicación a los hechos.
4. Fuentes favorables.
5. Contraargumentos previsibles.
6. Respuesta a cada contraargumento.
7. Prueba necesaria.
8. Riesgos y puntos débiles.
""",
        "Abogado contrario": """
Asumí la mejor posición posible de la contraparte y desarrollá:
1. Tesis adversa.
2. Objeciones jurídicas.
3. Objeciones fácticas.
4. Deficiencias probatorias.
5. Defensas procesales.
6. Precedentes o fuentes adversas.
7. Preguntas críticas.
8. Medidas para neutralizar esos argumentos.
""",
        "Redacción de escrito": """
Prepará una propuesta de redacción jurídica basada exclusivamente en los hechos y fuentes aportados.
Organizá el texto por capítulos, citá como [FUENTE N] y marcá con [INFORMACIÓN FALTANTE]
todo dato indispensable que no haya sido suministrado.
""",
        "Análisis de jurisprudencia": """
Analizá los fallos o criterios jurisprudenciales recuperados e identificá:
1. Hechos relevantes.
2. Cuestión jurídica.
3. Argumentos de las partes.
4. Decisión.
5. Ratio decidendi.
6. Obiter dicta.
7. Votos y disidencias.
8. Alcance y límites.
9. Utilidad práctica.
10. Relación con las demás fuentes.
""",
        "Comparación de criterios": """
Compará las fuentes e identificá:
1. Coincidencias.
2. Contradicciones.
3. Diferencias fácticas.
4. Diferencias normativas.
5. Autoridad relativa.
6. Evolución temporal.
7. Posibilidades de distinguir los precedentes.
8. Criterio más sólido para el caso.
""",
        "Estrategia procesal": """
Proponé una estrategia procesal fundada e incluí:
1. Pretensión principal y subsidiaria.
2. Orden de los planteos.
3. Riesgos de admisibilidad.
4. Defensas previsibles.
5. Prueba necesaria.
6. Medidas urgentes.
7. Próximos pasos.
8. Alternativas frente a un resultado adverso.
""",
    }

    def __init__(self, interpreted_search, query_interpreter):
        self.search = interpreted_search
        self.interpreter = query_interpreter
        self.extractor = DocumentExtractor()

    def build_research_package(
        self,
        query: str,
        facts: str = "",
        objective: str = "Investigación jurídica",
        additional_instruction: str = "",
        max_sources: int | None = None,
    ) -> ContextPackage:
        if not query.strip():
            raise ValueError("La consulta no puede estar vacía.")

        interpretation = self.interpreter.interpret(query)
        limit = max_sources or SETTINGS.context_builder_max_sources

        results = self.search.search(
            interpretation,
            limit=max(limit * 2, limit),
        )
        selected = self._select_sources(results, limit)

        if not selected:
            raise RuntimeError(
                "LexIA no encontró fuentes para preparar el contexto."
            )

        objective_text = self.TASKS.get(
            objective,
            self.TASKS["Investigación jurídica"],
        ).strip()

        interpretation_dict = interpretation.to_dict()
        sources_text = self._render_sources(selected)
        created_at = datetime.now().isoformat(timespec="seconds")
        title = self._safe_title(query)

        content = f"""# PAQUETE DE INVESTIGACIÓN JURÍDICA — LEXIA

## REGLAS OBLIGATORIAS

{self.BASE_RULES}

## OBJETIVO

{objective}

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

## INDICACIÓN ADICIONAL

{additional_instruction.strip() or '[No se agregó una indicación adicional]'}

## TAREA

{objective_text}

## FUENTES SELECCIONADAS POR LEXIA

{sources_text}

## CONTROL FINAL

Antes de responder, verificá que cada afirmación jurídica relevante tenga una cita [FUENTE N].
No uses fuentes externas ni conocimiento no contenido en este paquete.
Si una cuestión no puede responderse con las fuentes disponibles, indicá expresamente qué información falta.
Comenzá directamente con el análisis jurídico.
"""

        return ContextPackage(
            title=title,
            content=content,
            sources=selected,
            created_at=created_at,
            character_count=len(content),
            objective=objective,
            query=query.strip(),
            facts=facts.strip(),
            interpretation=interpretation_dict,
            document_count=len(results),
            selected_count=self._document_source_count(selected),
        )

    def build_document_package(
        self,
        path: str | Path,
        objective: str = "Análisis de jurisprudencia",
        instruction: str = "",
        document_type: str = "Detección automática",
    ) -> ContextPackage:
        extraction = self.extractor.extract(path)
        text = extraction.text.strip()

        if not text:
            raise RuntimeError(
                "No fue posible extraer texto del documento."
            )

        text = text[: SETTINGS.context_builder_upload_max_chars]
        filename = Path(path).name
        created_at = datetime.now().isoformat(timespec="seconds")
        objective_text = self.TASKS.get(
            objective,
            self.TASKS["Análisis de jurisprudencia"],
        ).strip()

        content = f"""# PAQUETE DE ANÁLISIS DOCUMENTAL — LEXIA

## REGLAS OBLIGATORIAS

{self.BASE_RULES}

## DOCUMENTO

- Nombre: {filename}
- Tipo indicado: {document_type}
- Método de extracción: {extraction.method}
- Páginas detectadas: {extraction.total_pages or 'No determinadas'}

## OBJETIVO

{objective}

## INDICACIÓN DEL USUARIO

{instruction.strip() or 'Analizá integralmente el documento.'}

## TAREA

{objective_text}

Además:
1. Resumí el documento.
2. Identificá su finalidad.
3. Separá hechos, argumentos y decisión o petición.
4. Enumerá normas, jurisprudencia y doctrina citadas.
5. Señalá fortalezas, debilidades, contradicciones y omisiones.
6. Explicá su utilidad práctica.
7. Cuando sea un fallo, distinguí ratio decidendi, obiter dicta, votos y disidencias.
8. Cuando sea un escrito, evaluá la coherencia entre hechos, derecho, prueba y petitorio.

## FUENTE 1

[FUENTE 1]
Documento: {filename}
Contenido:
{text}

## CONTROL FINAL

Respondé directamente en español.
No revises este paquete ni preguntes qué debe hacerse con él.
No inventes información ausente del documento.
Citá las afirmaciones relevantes como [FUENTE 1] y, cuando sea posible, indicá la página.
"""

        return ContextPackage(
            title=f"Analisis_{self._safe_title(Path(path).stem)}",
            content=content,
            sources=[],
            created_at=created_at,
            character_count=len(content),
            objective=objective,
            query=f"Analizar el documento {filename}",
            facts="",
            interpretation={
                "document_type": document_type,
                "extraction_method": extraction.method,
                "pages": extraction.total_pages,
            },
            document_count=1,
            selected_count=1,
        )

    def save(self, package: ContextPackage) -> dict[str, Path]:
        SETTINGS.context_builder_exports_path.mkdir(
            parents=True,
            exist_ok=True,
        )

        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        base_name = f"{stamp}_{package.title}"

        lexia_path = (
            SETTINGS.context_builder_exports_path
            / f"{base_name}.lexia"
        )
        txt_path = (
            SETTINGS.context_builder_exports_path
            / f"{base_name}.txt"
        )
        manifest_path = (
            SETTINGS.context_builder_exports_path
            / f"{base_name}.json"
        )

        lexia_path.write_text(package.content, encoding="utf-8")
        txt_path.write_text(package.content, encoding="utf-8")
        manifest_path.write_text(
            json.dumps(
                package.metadata(),
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

        return {
            "lexia": lexia_path,
            "txt": txt_path,
            "manifest": manifest_path,
        }

    def curate_package(
        self,
        package: ContextPackage,
        selected_indices: list[int],
    ) -> ContextPackage:
        """Reconstruye el contexto con un subconjunto sin repetir la búsqueda."""
        source_count = len(package.sources)
        normalized_indices: list[int] = []
        seen: set[int] = set()
        for value in selected_indices:
            index = int(value)
            if 0 <= index < source_count and index not in seen:
                normalized_indices.append(index)
                seen.add(index)

        if not normalized_indices:
            raise ValueError(
                "Seleccioná al menos una fuente para preparar el contexto."
            )

        selected_sources = [
            package.sources[index]
            for index in normalized_indices
        ]
        curated_content = self._curate_source_section(
            package.content,
            normalized_indices,
            selected_sources,
        )

        return replace(
            package,
            content=curated_content,
            sources=selected_sources,
            character_count=len(curated_content),
            selected_count=self._document_source_count(selected_sources),
        )

    def _curate_source_section(
        self,
        content: str,
        selected_indices: list[int],
        selected_sources: list[SearchResult],
    ) -> str:
        # Las fichas se eligen por fragmento en la interfaz, pero el paquete
        # final agrupa todos los fragmentos del mismo archivo bajo una sola
        # referencia [FUENTE N].
        rendered = self._render_sources(selected_sources)
        formats = (
            (
                "\nFUENTES\n\n",
                "\n\nESTRUCTURA DE LA RESPUESTA\n",
            ),
            (
                "\n## FUENTES SELECCIONADAS POR LEXIA\n\n",
                "\n\n## CONTROL FINAL\n",
            ),
        )

        for start_marker, end_marker in formats:
            start = content.find(start_marker)
            if start < 0:
                continue
            section_start = start + len(start_marker)
            end = content.find(end_marker, section_start)
            if end < 0:
                continue
            return content[:section_start] + rendered + content[end:]

        raise ValueError(
            "El contexto no contiene una sección de fuentes compatible."
        )


    def _select_sources(
        self,
        results: list[SearchResult],
        limit: int,
    ) -> list[SearchResult]:
        selected: list[SearchResult] = []
        seen_fragments: set[tuple[str, int]] = set()

        for result in results:
            path_key = str(result.document_path).casefold()
            key = (path_key, result.fragment_index)
            if key in seen_fragments:
                continue

            selected.append(result)
            seen_fragments.add(key)

            if len(selected) >= limit:
                break

        return selected

    @staticmethod
    def _document_groups(results):
        groups = []
        positions = {}

        for result in results or []:
            key = str(result.document_path).casefold()
            position = positions.get(key)
            if position is None:
                positions[key] = len(groups)
                groups.append([result])
            else:
                groups[position].append(result)

        return groups

    @classmethod
    def _document_source_count(cls, results) -> int:
        return len(cls._document_groups(results))

    def _render_sources(
        self,
        results: list[SearchResult],
    ) -> str:
        blocks: list[str] = []
        total_chars = 0

        for number, fragments in enumerate(
            self._document_groups(results),
            start=1,
        ):
            first = fragments[0]
            metadata = first.metadata or {}
            excerpts = []

            for fragment_number, result in enumerate(fragments, start=1):
                text = " ".join(result.text.split())
                text = text[: SETTINGS.context_builder_max_chars_per_source]
                excerpts.append(
                    f"FRAGMENTO {fragment_number}\n"
                    f"Ubicación: {result.page_label}\n"
                    f"Contenido: {text}"
                )

            block = (
                f"[FUENTE {number}]\n"
                f"Documento: {first.document_name}\n"
                f"Categoría: {first.category}\n"
                f"Tribunal: {metadata.get('court', 'No detectado')}\n"
                f"Fecha: {metadata.get('date', 'No detectada')}\n"
                f"Ruta local: {first.document_path}\n"
                f"Fragmentos seleccionados: {len(fragments)}\n\n"
                + "\n\n".join(excerpts)
            )

            if (
                blocks
                and total_chars + len(block)
                > SETTINGS.context_builder_max_total_chars
            ):
                break

            blocks.append(block)
            total_chars += len(block)

        return "\n\n".join(blocks)


    def _safe_title(self, text: str) -> str:
        clean = re.sub(
            r"[^A-Za-zÁÉÍÓÚÑáéíóúñ0-9 _-]+",
            "",
            text,
        )
        clean = "_".join(clean.split())[:75]
        return clean or "consulta_lexia"
