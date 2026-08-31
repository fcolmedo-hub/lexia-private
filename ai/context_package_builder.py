import json
import re
import unicodedata
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

    LONG_DOCUMENT_TASK = """
Trabajá con los pasajes seleccionados del libro o documento doctrinario y con las Indicaciones del usuario.
1. Identificá qué pasajes responden directamente a las Indicaciones.
2. Agrupá los pasajes por tema, capítulo o sección cuando el propio texto permita reconocerlos.
3. Explicá la tesis o desarrollo doctrinario de cada grupo.
4. Señalá posiciones, excepciones, distinciones, requisitos y consecuencias que aparezcan en el texto.
5. Conservá las referencias [FUENTE N] de cada pasaje.
6. No resumas partes del libro ajenas a las Indicaciones.
7. Si los pasajes recuperados no alcanzan para responder, indicá expresamente la insuficiencia.
""".strip()

    _STOPWORDS = {
        "para", "como", "donde", "desde", "sobre", "entre", "hasta", "este", "esta", "estos", "estas",
        "aquel", "aquella", "del", "las", "los", "una", "uno", "unos", "unas", "que", "con", "por",
        "sin", "sus", "sea", "son", "ser", "hay", "muy", "mas", "más", "pero", "porque", "cuando",
        "cual", "cuál", "todo", "toda", "todos", "todas", "documento", "libro", "doctrina", "informacion",
        "información", "indicacion", "indicación", "indicaciones", "tema", "habla", "hablen", "referido",
    }

    def __init__(self, interpreted_search, query_interpreter):
        self.search = interpreted_search
        self.interpreter = query_interpreter
        self.extractor = DocumentExtractor()

        # KnowledgeContextPackageBuilder redefine build_documents_package().
        # El estudio UI2 usa ese método incluso para un solo archivo. Para
        # Libro/Doctrina derivamos ese caso al selector temático de este
        # builder, sin alterar el comportamiento histórico de documentos
        # múltiples ni de los demás tipos documentales.
        inherited_multi_builder = getattr(self, "build_documents_package", None)
        if callable(inherited_multi_builder):
            def _document_package_router(
                documents,
                objective: str = "Análisis de jurisprudencia",
                instruction: str = "",
                document_type: str = "Detección automática",
            ):
                items = list(documents or [])
                if (
                    self._normalize(document_type) in {"libro", "doctrina"}
                    and len(items) == 1
                ):
                    item = items[0]
                    path = item[0] if isinstance(item, (tuple, list)) else item
                    return ContextPackageBuilder.build_document_package(
                        self,
                        path=path,
                        objective=objective,
                        instruction=instruction,
                        document_type=document_type,
                    )
                return inherited_multi_builder(
                    documents=items,
                    objective=objective,
                    instruction=instruction,
                    document_type=document_type,
                )

            self.build_documents_package = _document_package_router

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
        results = self.search.search(interpretation, limit=max(limit * 2, limit))
        selected = self._select_sources(results, limit)
        if not selected:
            raise RuntimeError("LexIA no encontró fuentes para preparar el contexto.")

        objective_text = self.TASKS.get(objective, self.TASKS["Investigación jurídica"]).strip()
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

## INDICACIONES

{additional_instruction.strip() or '[No se agregaron indicaciones]'}

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
            selected_count=len(selected),
        )

    def build_document_package(
        self,
        path: str | Path,
        objective: str = "Análisis de jurisprudencia",
        instruction: str = "",
        document_type: str = "Detección automática",
    ) -> ContextPackage:
        extraction = self.extractor.extract(path)
        full_text = extraction.text.strip()
        if not full_text:
            raise RuntimeError("No fue posible extraer texto del documento.")

        filename = Path(path).name
        created_at = datetime.now().isoformat(timespec="seconds")
        long_document = self._normalize(document_type) in {"libro", "doctrina"}
        focused = long_document and bool(instruction.strip())

        if focused:
            passages = self._focused_document_passages(
                full_text,
                instruction,
                total_pages=extraction.total_pages,
            )
            if not passages:
                raise RuntimeError(
                    "LexIA no encontró pasajes del documento relacionados con las Indicaciones. "
                    "Probá con términos más amplios o agregá conceptos relacionados."
                )
            sources_text = self._render_document_passages(filename, passages)
            objective_text = self.LONG_DOCUMENT_TASK
            source_count = len(passages)
            mode = "selección temática de pasajes"
        else:
            text = full_text[: SETTINGS.context_builder_upload_max_chars]
            sources_text = (
                f"[FUENTE 1]\nDocumento: {filename}\nContenido:\n{text}"
            )
            objective_text = self.TASKS.get(
                objective,
                self.TASKS["Análisis de jurisprudencia"],
            ).strip()
            source_count = 1
            mode = "análisis documental"

        content = f"""# PAQUETE DE ANÁLISIS DOCUMENTAL — LEXIA

## REGLAS OBLIGATORIAS

{self.BASE_RULES}

## DOCUMENTO

- Nombre: {filename}
- Tipo indicado: {document_type}
- Método de extracción: {extraction.method}
- Páginas detectadas: {extraction.total_pages or 'No determinadas'}
- Modo de recuperación: {mode}

## OBJETIVO

{objective}

## INDICACIONES

{instruction.strip() or 'Analizá integralmente el documento.'}

## TAREA

{objective_text}

## FUENTES SELECCIONADAS POR LEXIA

{sources_text}

## CONTROL FINAL

Respondé directamente en español.
No revises este paquete ni preguntes qué debe hacerse con él.
No inventes información ausente del documento.
Citá cada afirmación relevante con la fuente concreta [FUENTE N].
En Libro y Doctrina, concentrá la respuesta en los pasajes recuperados por su relación con las Indicaciones.
"""

        return ContextPackage(
            title=f"Analisis_{self._safe_title(Path(path).stem)}",
            content=content,
            sources=[],
            created_at=created_at,
            character_count=len(content),
            objective=objective,
            query=(
                f"Localizar en {filename}: {instruction.strip()}"
                if focused else f"Analizar el documento {filename}"
            ),
            facts="",
            interpretation={
                "document_type": document_type,
                "extraction_method": extraction.method,
                "pages": extraction.total_pages,
                "mode": mode,
                "indications": instruction.strip(),
                "passages": source_count,
            },
            document_count=1,
            selected_count=source_count,
        )

    def _focused_document_passages(self, text: str, instruction: str, total_pages=None) -> list[dict]:
        chunks = self._document_chunks(text)
        terms, phrases = self._instruction_terms(instruction)
        if not chunks or not terms:
            return []

        scored = []
        for index, chunk in enumerate(chunks):
            normalized = self._normalize(chunk["text"])
            if not normalized:
                continue
            score = 0.0
            matched = set()
            for term in terms:
                count = len(re.findall(r"(?<!\w)" + re.escape(term) + r"(?!\w)", normalized))
                if count:
                    matched.add(term)
                    score += min(count, 8) * (2.0 if len(term) >= 7 else 1.35)
            for phrase in phrases:
                if len(phrase) >= 5 and phrase in normalized:
                    score += 10.0
            coverage = len(matched) / max(1, len(terms))
            score += coverage * 12.0
            if score <= 0:
                continue
            scored.append((score, coverage, index, chunk))

        if not scored:
            return []

        scored.sort(key=lambda item: (item[0], item[1]), reverse=True)
        max_sources = min(24, max(8, int(getattr(SETTINGS, "context_builder_max_sources", 14) or 14)))
        max_chars = int(getattr(SETTINGS, "context_builder_max_total_chars", 90000) or 90000)
        selected = []
        selected_indices = set()
        total_chars = 0

        for score, coverage, index, chunk in scored:
            if index in selected_indices:
                continue
            passage_text = chunk["text"].strip()
            per_source = int(getattr(SETTINGS, "context_builder_max_chars_per_source", 6500) or 6500)
            if len(passage_text) > per_source:
                passage_text = passage_text[:per_source].rstrip() + " […]"
            if selected and total_chars + len(passage_text) > max_chars:
                break

            page = None
            try:
                pages = int(total_pages or 0)
                if pages > 0 and len(text) > 0:
                    page = min(pages, max(1, int((chunk["start"] / len(text)) * pages) + 1))
            except Exception:
                page = None

            selected.append({
                "text": passage_text,
                "start": chunk["start"],
                "end": chunk["end"],
                "page": page,
                "score": round(score, 2),
            })
            selected_indices.add(index)
            total_chars += len(passage_text)
            if len(selected) >= max_sources:
                break

        selected.sort(key=lambda item: item["start"])
        return selected

    def _document_chunks(self, text: str) -> list[dict]:
        text = text.strip()
        if not text:
            return []
        target = 3600
        overlap = 650
        chunks = []
        start = 0
        length = len(text)
        while start < length:
            raw_end = min(length, start + target)
            end = raw_end
            if raw_end < length:
                candidates = [
                    text.rfind("\n\n", start + int(target * 0.55), raw_end),
                    text.rfind(". ", start + int(target * 0.55), raw_end),
                    text.rfind("; ", start + int(target * 0.55), raw_end),
                ]
                best = max(candidates)
                if best > start:
                    end = best + (2 if text[best:best + 2] in {". ", "; "} else 0)
            chunk_text = text[start:end].strip()
            if chunk_text:
                chunks.append({"text": chunk_text, "start": start, "end": end})
            if end >= length:
                break
            start = max(start + 1, end - overlap)
        return chunks

    def _instruction_terms(self, instruction: str) -> tuple[list[str], list[str]]:
        normalized_instruction = self._normalize(instruction)
        terms = set(self._meaningful_terms(normalized_instruction))
        phrases = {normalized_instruction} if normalized_instruction else set()

        try:
            interpreted = self.interpreter.interpret(instruction)
            values = [
                getattr(interpreted, "area", ""),
                getattr(interpreted, "main_institute", ""),
                getattr(interpreted, "claim_or_goal", ""),
                getattr(interpreted, "jurisdiction", ""),
            ]
            for attr in ("conduct", "damages", "procedural_issues", "subtopics"):
                values.extend(getattr(interpreted, attr, []) or [])
            for value in values:
                normalized = self._normalize(value)
                if not normalized:
                    continue
                phrases.add(normalized)
                terms.update(self._meaningful_terms(normalized))
        except Exception:
            pass

        return sorted(terms), sorted(phrases, key=len, reverse=True)

    def _meaningful_terms(self, text: str) -> list[str]:
        return [
            token for token in re.findall(r"[a-z0-9]+", text)
            if len(token) >= 3 and token not in self._STOPWORDS
        ]

    def _normalize(self, value) -> str:
        text = unicodedata.normalize("NFKD", str(value or ""))
        text = "".join(ch for ch in text if not unicodedata.combining(ch)).lower()
        text = re.sub(r"[^a-z0-9]+", " ", text)
        return " ".join(text.split())

    def _render_document_passages(self, filename: str, passages: list[dict]) -> str:
        blocks = []
        for number, passage in enumerate(passages, start=1):
            location = (
                f"Página aproximada: {passage['page']}"
                if passage.get("page") else
                f"Posición aproximada: caracteres {passage['start'] + 1}-{passage['end']}"
            )
            blocks.append(
                f"[FUENTE {number}]\n"
                f"Documento: {filename}\n"
                f"{location}\n"
                f"Pasaje relacionado con las Indicaciones:\n{passage['text']}"
            )
        return "\n\n".join(blocks)

    def save(self, package: ContextPackage) -> dict[str, Path]:
        SETTINGS.context_builder_exports_path.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        base_name = f"{stamp}_{package.title}"
        lexia_path = SETTINGS.context_builder_exports_path / f"{base_name}.lexia"
        txt_path = SETTINGS.context_builder_exports_path / f"{base_name}.txt"
        manifest_path = SETTINGS.context_builder_exports_path / f"{base_name}.json"
        lexia_path.write_text(package.content, encoding="utf-8")
        txt_path.write_text(package.content, encoding="utf-8")
        manifest_path.write_text(json.dumps(package.metadata(), ensure_ascii=False, indent=2), encoding="utf-8")
        return {"lexia": lexia_path, "txt": txt_path, "manifest": manifest_path}

    def curate_package(
        self,
        package: ContextPackage,
        selected_indices: list[int],
    ) -> ContextPackage:
        source_count = len(package.sources)
        normalized_indices = []
        seen = set()
        for value in selected_indices:
            index = int(value)
            if 0 <= index < source_count and index not in seen:
                normalized_indices.append(index)
                seen.add(index)
        if not normalized_indices:
            raise ValueError("Seleccioná al menos una fuente para preparar el contexto.")
        selected_sources = [package.sources[index] for index in normalized_indices]
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
            selected_count=len(selected_sources),
        )

    def _curate_source_section(
        self,
        content: str,
        selected_indices: list[int],
        selected_sources: list[SearchResult],
    ) -> str:
        formats = (
            ("\nFUENTES\n\n", "\n\nESTRUCTURA DE LA RESPUESTA\n"),
            ("\n## FUENTES SELECCIONADAS POR LEXIA\n\n", "\n\n## CONTROL FINAL\n"),
        )
        for start_marker, end_marker in formats:
            start = content.find(start_marker)
            if start < 0:
                continue
            section_start = start + len(start_marker)
            end = content.find(end_marker, section_start)
            if end < 0:
                continue
            section = content[section_start:end].strip()
            block_matches = list(re.finditer(r"(?m)^\[FUENTE\s+\d+\]\s*$", section))
            if not block_matches:
                continue
            blocks = []
            for position, match in enumerate(block_matches):
                block_end = block_matches[position + 1].start() if position + 1 < len(block_matches) else len(section)
                blocks.append(section[match.start():block_end].strip())
            if max(selected_indices) >= len(blocks):
                continue
            curated_blocks = []
            for new_number, original_index in enumerate(selected_indices, start=1):
                block = re.sub(
                    r"^\[FUENTE\s+\d+\]",
                    f"[FUENTE {new_number}]",
                    blocks[original_index],
                    count=1,
                )
                curated_blocks.append(block)
            return content[:section_start] + "\n\n".join(curated_blocks) + content[end:]

        rendered = self._render_sources(selected_sources)
        if "## FUENTES SELECCIONADAS POR LEXIA" in content:
            start_marker = "\n## FUENTES SELECCIONADAS POR LEXIA\n\n"
            end_marker = "\n\n## CONTROL FINAL\n"
            start = content.find(start_marker)
            end = content.find(end_marker, start + len(start_marker))
            if start >= 0 and end >= 0:
                section_start = start + len(start_marker)
                return content[:section_start] + rendered + content[end:]
        raise ValueError("El contexto no contiene una sección de fuentes compatible.")

    def _select_sources(self, results: list[SearchResult], limit: int) -> list[SearchResult]:
        selected = []
        seen_fragments = set()
        per_document = {}
        for result in results:
            path_key = str(result.document_path).lower()
            key = (path_key, result.fragment_index)
            if key in seen_fragments:
                continue
            if per_document.get(path_key, 0) >= 2:
                continue
            selected.append(result)
            seen_fragments.add(key)
            per_document[path_key] = per_document.get(path_key, 0) + 1
            if len(selected) >= limit:
                break
        return selected

    def _render_sources(self, results: list[SearchResult]) -> str:
        blocks = []
        total_chars = 0
        for number, result in enumerate(results, start=1):
            metadata = result.metadata or {}
            text = " ".join(result.text.split())
            text = text[: SETTINGS.context_builder_max_chars_per_source]
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
            if blocks and total_chars + len(block) > SETTINGS.context_builder_max_total_chars:
                break
            blocks.append(block)
            total_chars += len(block)
        return "\n\n".join(blocks)

    def _safe_title(self, text: str) -> str:
        clean = re.sub(r"[^A-Za-zÁÉÍÓÚÑáéíóúñ0-9 _-]+", "", text)
        clean = "_".join(clean.split())[:75]
        return clean or "consulta_lexia"
