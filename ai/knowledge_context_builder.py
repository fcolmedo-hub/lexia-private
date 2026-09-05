from contextlib import nullcontext
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

from ai.context_package_builder import (
    ContextPackage,
    ContextPackageBuilder,
)
from config.settings import SETTINGS
from ai.legal_query_expander import LegalQueryExpander
from ai.legal_authority_ranker import LegalAuthorityRanker
from ai.intelligent_context_selector import IntelligentContextSelector
from storage.catalog import DocumentCatalog


class KnowledgeContextPackageBuilder(
    ContextPackageBuilder
):
    """
    Context Builder de una sola pasada.

    Interpreta, busca, ordena y construye el expediente una sola vez.
    No vuelve a invocar al ContextPackageBuilder base para repetir la
    búsqueda.
    """

    def __init__(
        self,
        interpreted_search,
        query_interpreter,
        knowledge_engine,
        performance_profiler=None,
    ):
        super().__init__(
            interpreted_search,
            query_interpreter,
        )
        self.knowledge = knowledge_engine
        self.performance_profiler = (
            performance_profiler
        )
        self.query_expander = LegalQueryExpander()
        self.legal_authority_ranker = LegalAuthorityRanker()
        self.context_selector = IntelligentContextSelector(
            max_per_document=None,
            similarity_threshold=float(
                getattr(
                    SETTINGS,
                    "context_builder_duplicate_similarity",
                    0.88,
                )
            ),
        )


    # >>> LEXIA FAST SEARCH 1.1 CONTEXT BUILDER
    @staticmethod
    def _fast_search_11_normalize_query(query: str) -> str:
        text = " ".join(str(query or "").strip().split())
        if not text:
            return ""

        tokens = text.split()
        folded = [t.casefold() for t in tokens]

        if len(tokens) % 2 == 0:
            half = len(tokens) // 2
            if folded[:half] == folded[half:]:
                text = " ".join(tokens[:half])
                tokens = text.split()

        compact = []
        last = None
        for token in tokens:
            key = token.casefold()
            if key != last:
                compact.append(token)
            last = key

        return " ".join(compact).strip()

    @classmethod
    def _fast_search_11_queries(cls, original_query, interpreter_queries, plan_queries):
        candidates = [original_query]
        candidates.extend(list(interpreter_queries or []))
        candidates.extend(list(plan_queries or []))

        output = []
        seen = set()

        for raw in candidates:
            normalized = cls._fast_search_11_normalize_query(raw)
            if not normalized:
                continue

            key = normalized.casefold()
            if key in seen:
                continue

            seen.add(key)
            output.append(normalized)

            if len(output) >= 4:
                break

        return output
    # <<< LEXIA FAST SEARCH 1.1 CONTEXT BUILDER

    def build_research_package(
        self,
        query: str,
        facts: str = "",
        objective: str = "Investigación jurídica",
        additional_instruction: str = "",
        max_sources: int | None = None,
    ) -> ContextPackage:
        if not query.strip():
            raise ValueError(
                "La consulta no puede estar vacía."
            )

        profiler = self.performance_profiler

        if profiler:
            profiler.start(query)

        try:
            limit = min(
                max_sources
                or SETTINGS.context_builder_max_sources,
                SETTINGS.context_builder_runtime_max_sources,
            )

            if (
                SETTINGS.knowledge_sync_on_context_build
                and getattr(
                    SETTINGS,
                    "knowledge_sync_before_search",
                    False,
                )
            ):
                with self._stage(
                    "knowledge_sync"
                ):
                    self.knowledge.sync_incremental(
                        rebuild_relations=False
                    )

            with self._stage(
                "query_interpretation"
            ):
                interpretation = (
                    self.interpreter.interpret(
                        query
                    )
                )

            with self._stage(
                "knowledge_plan"
            ):
                plan = self.knowledge.plan(
                    query,
                    interpretation,
                )

            with self._stage(
                "query_expansion_2_0"
            ):
                interpretation.search_queries = (
                    self.query_expander.expand(
                        query,
                        interpretation.search_queries,
                        max_queries=int(
                            getattr(
                                SETTINGS,
                                "interpreter_max_queries",
                                10,
                            )
                        ),
                    )
                )

            # >>> LEXIA FAST SEARCH 1.1 CONTEXT BUILDER QUERY POLICY
            interpretation.search_queries = self._fast_search_11_queries(
                query,
                interpretation.search_queries,
                plan.search_queries,
            )
            # <<< LEXIA FAST SEARCH 1.1 CONTEXT BUILDER QUERY POLICY

            candidate_limit = min(
                SETTINGS.context_builder_max_candidates,
                max(
                    limit
                    * SETTINGS
                    .knowledge_candidate_multiplier,
                    limit,
                ),
            )

            if profiler:
                profiler.metric(
                    "requested_max_sources",
                    limit,
                )
                profiler.metric(
                    "search_query_count",
                    len(
                        interpretation.search_queries
                    ),
                )
                profiler.metric(
                    "search_queries",
                    list(
                        interpretation.search_queries
                    ),
                )
                profiler.metric(
                    "query_interpreter_2_0",
                    True,
                )
                profiler.metric(
                    "candidate_limit",
                    candidate_limit,
                )

            with self._stage(
                "single_interpreted_search",
                query_count=len(
                    interpretation.search_queries
                ),
                candidate_limit=candidate_limit,
            ):
                candidates = self.search.search(
                    interpretation,
                    limit=candidate_limit,
                )

            ranking_pool_limit = min(
                len(candidates),
                max(
                    limit * int(
                        getattr(
                            SETTINGS,
                            "context_builder_selection_pool_multiplier",
                            3,
                        )
                    ),
                    limit,
                ),
            )

            with self._stage(
                "knowledge_ranking",
                candidate_count=len(candidates),
                selected_limit=limit,
                ranking_pool_limit=ranking_pool_limit,
            ):
                ranked = (
                    self.knowledge.rank_sources(
                        candidates,
                        plan,
                        ranking_pool_limit,
                    )
                )

            with self._stage(
                "legal_authority_ranking",
                ranked_count=len(ranked),
            ):
                ranked = self.legal_authority_ranker.rerank(
                    ranked,
                    plan,
                )

            with self._stage(
                "context_intelligent_selection",
                ranked_count=len(ranked),
                selected_limit=limit,
            ):
                selected_ranked = self.context_selector.select(
                    ranked,
                    limit,
                )
                selected = [
                    item[1]
                    for item in selected_ranked
                ]

            if not selected:
                raise RuntimeError(
                    "LexIA no encontró fuentes para "
                    "construir el expediente."
                )

            with self._stage(
                "context_render"
            ):
                package = self._build_package(
                    query=query,
                    facts=facts,
                    objective=objective,
                    additional_instruction=(
                        additional_instruction
                    ),
                    interpretation=interpretation,
                    plan=plan,
                    candidates=candidates,
                    selected=selected,
                    ranked=selected_ranked,
                )

            if profiler:
                profiler.metric(
                    "candidates_recovered",
                    len(candidates),
                )
                profiler.metric(
                    "sources_selected",
                    len(selected),
                )
                profiler.metric(
                    "distinct_documents_selected",
                    self.context_selector.last_stats.distinct_documents,
                )
                profiler.metric(
                    "distinct_categories_selected",
                    self.context_selector.last_stats.distinct_categories,
                )
                profiler.metric(
                    "near_duplicates_skipped",
                    self.context_selector.last_stats.near_duplicates_skipped,
                )
                profiler.metric(
                    "same_document_fragments_skipped",
                    self.context_selector.last_stats.same_document_skipped,
                )
                profiler.metric(
                    "context_character_count",
                    package.character_count,
                )
                profiler.metric(
                    "duplicate_second_pass",
                    False,
                )
                profiler.finish()

            return package

        except Exception as error:
            if profiler:
                profiler.finish(error)
            raise

    def build_documents_package(
        self,
        documents,
        objective: str = "Análisis de jurisprudencia",
        instruction: str = "",
        document_type: str = "Detección automática",
    ) -> ContextPackage:
        """Construye un único Contexto.txt con varios documentos."""
        items = list(documents or [])

        if not items:
            raise ValueError(
                "Seleccioná al menos un documento."
            )

        created_at = datetime.now().isoformat(
            timespec="seconds"
        )
        objective_text = self.TASKS.get(
            objective,
            self.TASKS["Análisis de jurisprudencia"],
        ).strip()

        normalized = []

        # El catálogo es la fuente de verdad para documentos que ya fueron
        # extraídos/OCR e indexados. No tiene sentido volver a abrir y extraer
        # el archivo físico en cada estudio si LexIA ya conserva texto válido.
        catalog = DocumentCatalog(SETTINGS.catalog_path)

        for item in items:
            if isinstance(item, (tuple, list)):
                path = Path(item[0])
                original_name = str(item[1])
            else:
                path = Path(item)
                original_name = path.name

            state = catalog.get_file_state(path)
            indexed_text = str(
                (state or {}).get("text_content") or ""
            ).strip()
            active_in_catalog = bool(
                state
                and not int((state or {}).get("is_deleted", 0) or 0)
            )

            if active_in_catalog and indexed_text:
                # Prioridad absoluta al contenido persistido: un error de
                # extracción histórico no invalida texto obtenido después
                # mediante OCR y ya incorporado correctamente al catálogo.
                extracted_text = indexed_text
                extraction_method = str(
                    (state or {}).get("extraction_method")
                    or "catalog"
                )
                detected_pages = (
                    (state or {}).get("total_pages")
                    or (state or {}).get("ocr_pages")
                    or "No determinadas"
                )
            else:
                # Fallback para archivos aún no indexados o sin texto
                # persistido: conservar el comportamiento tradicional.
                extraction = self.extractor.extract(path)
                extracted_text = extraction.text.strip()

                if not extracted_text:
                    catalog_error = str(
                        (state or {}).get("extraction_error") or ""
                    ).strip()
                    detail = (
                        f" {catalog_error}"
                        if catalog_error
                        else ""
                    )
                    raise RuntimeError(
                        "No fue posible extraer texto de "
                        f"'{original_name}'.{detail}"
                    )

                extraction_method = extraction.method
                detected_pages = (
                    extraction.total_pages
                    or "No determinadas"
                )

            normalized.append(
                {
                    "name": original_name,
                    "method": extraction_method,
                    "pages": detected_pages,
                    "text": extracted_text,
                }
            )

        max_total = int(
            SETTINGS.context_builder_max_total_chars
        )
        per_document_limit = int(
            SETTINGS.context_builder_upload_max_chars
        )

        reserved = min(
            12000,
            max(
                3000,
                int(max_total * 0.08),
            ),
        )
        available_for_sources = max(
            len(normalized) * 1000,
            max_total - reserved,
        )
        fair_share = max(
            1000,
            available_for_sources // len(normalized),
        )
        per_source_budget = min(
            per_document_limit,
            fair_share,
        )

        source_blocks = []

        for number, item in enumerate(
            normalized,
            start=1,
        ):
            source_text = item["text"][
                :per_source_budget
            ]

            if len(item["text"]) > len(source_text):
                source_text += (
                    "\n\n[CONTENIDO TRUNCADO POR LÍMITE "
                    "DEL CONTEXTO]"
                )

            source_blocks.append(
                (
                    f"## FUENTE {number}\n\n"
                    f"[FUENTE {number}]\n"
                    f"Documento: {item['name']}\n"
                    f"Tipo indicado: {document_type}\n"
                    f"Método de extracción: "
                    f"{item['method']}\n"
                    f"Páginas detectadas: "
                    f"{item['pages']}\n"
                    f"Contenido:\n{source_text}"
                )
            )

        document_names = [
            item["name"]
            for item in normalized
        ]

        document_index = "\n".join(
            f"- [FUENTE {index}] {name}"
            for index, name in enumerate(
                document_names,
                start=1,
            )
        )

        sources_text = "\n\n".join(
            source_blocks
        )

        working_criteria = (
            "Trabajá únicamente con los documentos incluidos debajo.\n"
            "No agregues hechos, normas, jurisprudencia, doctrina "
            "ni argumentos externos.\n"
            "Toda afirmación jurídica o fáctica debe indicar la "
            "fuente correspondiente como [FUENTE N].\n"
            "Si los documentos no permiten responder un punto, "
            "indicá exactamente qué información falta.\n"
            "Comenzá directamente con el análisis, sin describir "
            "este expediente ni pedir aclaraciones previas."
        )

        content = f"""# LEXIA — EXPEDIENTE DE ANÁLISIS DOCUMENTAL MÚLTIPLE

## IDENTIFICACIÓN

- Formato: LexIA Context Package
- Versión: 1.0
- Fecha de creación: {created_at}
- Documentos seleccionados: {len(document_names)}
- Tipo indicado: {document_type}
- Objetivo: {objective}

## DOCUMENTOS INCLUIDOS

{document_index}

## INSTRUCCIÓN PRINCIPAL PARA CHATGPT

{working_criteria}

## TAREA ESPECÍFICA

{objective_text}

## INDICACIÓN ADICIONAL DEL USUARIO

{instruction.strip() or "[No se agregó una indicación adicional]"}

## REGLAS ESPECÍFICAS PARA DOCUMENTOS

- Analizá los documentos en conjunto y también individualmente cuando corresponda.
- Identificá coincidencias, diferencias, contradicciones y relaciones entre ellos.
- No atribuyas a un documento afirmaciones presentes únicamente en otro.
- Conservá la distinción entre hechos, argumentos y decisiones.
- Citá cada documento como [FUENTE N] y, cuando sea posible, indicá la página.

## FUENTES

{sources_text}

## FORMATO MÍNIMO DE LA RESPUESTA

1. Resumen ejecutivo.
2. Identificación y finalidad de cada documento.
3. Relación entre los documentos.
4. Hechos y antecedentes.
5. Cuestiones jurídicas o pretensiones.
6. Argumentos centrales.
7. Normas, jurisprudencia y doctrina citadas.
8. Coincidencias y diferencias.
9. Fortalezas.
10. Debilidades, contradicciones u omisiones.
11. Utilidad práctica.
12. Información que no surge de los documentos.

## ORDEN FINAL

Comenzá inmediatamente con el análisis conjunto.
No preguntes qué debe hacerse con los archivos.
"""

        return ContextPackage(
            title="Analisis_documentos",
            content=content,
            sources=[],
            created_at=created_at,
            character_count=len(content),
            objective=objective,
            query=(
                "Análisis conjunto de documentos: "
                + ", ".join(document_names)
            ),
            facts="",
            interpretation={
                "document_type": document_type,
                "documents": document_names,
                "per_source_budget": (
                    per_source_budget
                ),
            },
            document_count=len(normalized),
            selected_count=len(normalized),
        )

    def build_research_candidates(
        self,
        query: str,
        facts: str = "",
        objective: str = "Investigación jurídica",
        additional_instruction: str = "",
        candidate_limit: int = 20,
        depth: str = "normal",
        ordering: str = "authority",
        exclusions=None,
        progress_callback=None,
    ) -> ContextPackage:
        """Recupera fuentes reales para que el usuario las confirme.

        El paquete devuelto conserva las fuentes ordenadas y se puede depurar
        después con ``curate_package`` sin ejecutar una segunda búsqueda.
        """
        if not query.strip():
            raise ValueError("La consulta no puede estar vacía.")

        limit = max(1, min(int(candidate_limit or 20), 20))
        depth = str(depth or "normal").strip().lower()
        ordering = str(ordering or "authority").strip().lower()

        def report(step: int, status: str, percentage: int) -> None:
            if progress_callback is not None:
                progress_callback(step, status, percentage)

        if (
            SETTINGS.knowledge_sync_on_context_build
            and getattr(SETTINGS, "knowledge_sync_before_search", False)
        ):
            with self._stage("knowledge_sync"):
                self.knowledge.sync_incremental(rebuild_relations=False)

        report(1, "Interpretando la consulta jurídica...", 12)
        with self._stage("query_interpretation"):
            interpretation = self.interpreter.interpret(query)
        with self._stage("knowledge_plan"):
            plan = self.knowledge.plan(query, interpretation)
        with self._stage("query_expansion_2_0"):
            interpretation.search_queries = self.query_expander.expand(
                query,
                interpretation.search_queries,
                max_queries=int(getattr(SETTINGS, "interpreter_max_queries", 10)),
            )

        interpretation.search_queries = self._fast_search_11_queries(
            query, interpretation.search_queries, plan.search_queries,
        )
        query_budget = {
            "quick": 1,
            "normal": 2,
            "complete": 3,
            "exhaustive": 4,
        }.get(depth, 2)
        interpretation.search_queries = interpretation.search_queries[:query_budget]
        recovered_limit = min(
            SETTINGS.context_builder_max_candidates,
            max(limit * SETTINGS.knowledge_candidate_multiplier, limit, limit + 12),
        )
        report(2, "Buscando fuentes en la biblioteca indexada...", 38)
        if depth == "quick":
            # La opción rápida consulta directamente el índice FTS5 de LexIA:
            # sigue usando la biblioteca real, pero evita las pasadas
            # semánticas, expansiones y rerankings costosos.
            with self._stage("quick_fts5_search", candidate_limit=recovered_limit):
                # Acceso directo al catálogo activo. Esta ruta no depende de
                # las capas de caché, hotfix o búsqueda semántica; el catálogo
                # es la fuente única de verdad para el índice FTS5.
                catalog_path = Path(SETTINGS.runtime_path) / "lexia_catalog.sqlite3"
                catalog = DocumentCatalog(catalog_path)
                fts_query = query
                rows = catalog.lexical_search(fts_query, recovered_limit)
                candidates = []
                for rank, row in enumerate(rows, start=1):
                    start = row.get("page_start")
                    end = row.get("page_end")
                    page_label = (
                        f"Páginas {start}-{end}" if start and end and start != end
                        else f"Página {start or end}" if start or end
                        else "Ubicación no determinada"
                    )
                    candidates.append(SimpleNamespace(
                        document_name=str(row.get("document_name", "Fuente sin nombre") or "Fuente sin nombre"),
                        document_path=Path(str(row.get("document_path", "") or "")),
                        category=str(row.get("category", "Sin categoría") or "Sin categoría"),
                        fragment_index=int(row.get("fragment_index", 0) or 0),
                        text=str(row.get("text_content", "") or ""),
                        score=1.0 / rank,
                        page_label=page_label,
                        metadata={},
                    ))
        else:
            with self._stage("single_interpreted_search", candidate_limit=recovered_limit):
                candidates = self.search.search(interpretation, limit=recovered_limit)

        # La interfaz puede excluir categorías completas o subcarpetas.  El
        # filtrado se aplica antes del ranking, la selección y la construcción
        # del paquete: ninguna fuente excluida llega al resultado final.
        normalized_exclusions = []
        for raw in exclusions or []:
            if not isinstance(raw, dict):
                continue
            category = str(raw.get("category", "") or "").strip().casefold()
            folder = str(raw.get("folder", "") or "").strip()
            if category or folder:
                normalized_exclusions.append((category, folder))

        def is_excluded(source) -> bool:
            source_category = str(getattr(source, "category", "") or "").strip().casefold()
            raw_path = str(getattr(source, "document_path", "") or "").strip()
            try:
                source_path = Path(raw_path).resolve(strict=False)
            except (OSError, ValueError):
                source_path = None
            for excluded_category, excluded_folder in normalized_exclusions:
                if excluded_category and source_category != excluded_category:
                    continue
                if not excluded_folder:
                    return True
                if source_path is None:
                    continue
                try:
                    folder_path = Path(excluded_folder).resolve(strict=False)
                    source_path.relative_to(folder_path)
                    return True
                except (OSError, ValueError):
                    continue
            return False

        if normalized_exclusions:
            candidates = [source for source in candidates if not is_excluded(source)]
            if not candidates:
                raise RuntimeError(
                    "No quedaron fuentes después de aplicar las carpetas excluidas."
                )
        # La búsqueda interpretada puede resultar demasiado estricta para
        # una consulta redactada en lenguaje natural. Antes de declarar que
        # no hay fuentes, se consulta el FTS5 real con términos significativos
        # de la consulta; el usuario siempre revisa y confirma las fuentes.
        if not candidates and depth != "quick":
            ignored_terms = {
                "para", "sobre", "desde", "entre", "contra", "cuando",
                "donde", "como", "cual", "cuáles", "tiene", "tienen",
                "debe", "deben", "puede", "pueden", "del", "las", "los",
                "una", "uno", "que", "por", "con", "sin", "ante",
            }
            fallback_terms = []
            seen_terms = set()
            for raw_term in query.split():
                term = "".join(
                    char for char in raw_term
                    if char.isalnum()
                ).casefold()
                if (
                    len(term) < 3
                    or term in ignored_terms
                    or term in seen_terms
                ):
                    continue
                fallback_terms.append(term)
                seen_terms.add(term)
                if len(fallback_terms) >= 10:
                    break

            if fallback_terms:
                report(
                    2,
                    "Ampliando la búsqueda en el índice documental...",
                    54,
                )
                fts_query = " OR ".join(fallback_terms)
                catalog = DocumentCatalog(
                    Path(SETTINGS.runtime_path)
                    / "lexia_catalog.sqlite3"
                )
                rows = catalog.lexical_search(
                    fts_query,
                    recovered_limit,
                )
                candidates = []
                for rank, row in enumerate(rows, start=1):
                    start = row.get("page_start")
                    end = row.get("page_end")
                    page_label = (
                        f"Páginas {start}-{end}"
                        if start and end and start != end
                        else f"Página {start or end}"
                        if start or end
                        else "Ubicación no determinada"
                    )
                    candidates.append(SimpleNamespace(
                        document_name=str(
                            row.get("document_name", "Fuente sin nombre")
                            or "Fuente sin nombre"
                        ),
                        document_path=Path(
                            str(row.get("document_path", "") or "")
                        ),
                        category=str(
                            row.get("category", "Sin categoría")
                            or "Sin categoría"
                        ),
                        fragment_index=int(
                            row.get("fragment_index", 0) or 0
                        ),
                        text=str(
                            row.get("text_content", "") or ""
                        ),
                        score=1.0 / rank,
                        page_label=page_label,
                        metadata={},
                    ))

        report(3, "Ordenando fuentes por el criterio seleccionado...", 66)
        if depth == "quick":
            selected = candidates[:limit]
            selected_ranked = [
                (position, source, [], "FTS5")
                for position, source in enumerate(selected, start=1)
            ]
        else:
            ranking_pool_limit = min(
                len(candidates),
                max(
                    limit * int(getattr(SETTINGS, "context_builder_selection_pool_multiplier", 3)),
                    limit,
                ),
            )
            with self._stage("knowledge_ranking", candidate_count=len(candidates)):
                ranked = self.knowledge.rank_sources(candidates, plan, ranking_pool_limit)
            with self._stage("legal_authority_ranking", ranked_count=len(ranked)):
                ranked = self.legal_authority_ranker.rerank(ranked, plan)
            with self._stage("context_intelligent_selection", selected_limit=limit):
                selected_ranked = self.context_selector.select(ranked, limit)
                if ordering == "relevance":
                    selected_ranked = sorted(
                        selected_ranked,
                        key=lambda item: float(getattr(item[1], "score", 0) or 0),
                        reverse=True,
                    )
                elif ordering == "recent":
                    selected_ranked = sorted(
                        selected_ranked,
                        key=lambda item: str((getattr(item[1], "metadata", {}) or {}).get("date", "")),
                        reverse=True,
                    )
                selected = [item[1] for item in selected_ranked]

        # Un selector muy conservador no debe transformar resultados reales
        # en una investigación vacía. Conservamos los primeros candidatos
        # obtenidos del índice, claramente sujetos a revisión del usuario.
        if not selected and candidates:
            selected = candidates[:limit]
            selected_ranked = [
                (
                    position,
                    source,
                    [],
                    "Coincidencia recuperada directamente",
                )
                for position, source in enumerate(selected, start=1)
            ]

        if not selected:
            raise RuntimeError(
                "No se encontraron fuentes en la biblioteca para esta "
                "consulta. Probá con palabras jurídicas más concretas."
            )

        # Veinte fichas deben entrar completas en el paquete candidato; luego
        # curate_package conserva exactamente las elegidas por el usuario.
        report(4, "Preparando las fuentes para tu revisión...", 90)
        package = self._build_package(
            query=query,
            facts=facts,
            objective=objective,
            additional_instruction=additional_instruction,
            interpretation=interpretation,
            plan=plan,
            candidates=candidates,
            selected=selected,
            ranked=selected_ranked,
            source_char_limit=2100,
        )
        report(4, "Fuentes listas para revisar.", 100)
        return package

    def _build_package(
        self,
        *,
        query,
        facts,
        objective,
        additional_instruction,
        interpretation,
        plan,
        candidates,
        selected,
        ranked,
        source_char_limit=None,
    ) -> ContextPackage:
        created_at = datetime.now().isoformat(
            timespec="seconds"
        )
        title = self._safe_title(query)
        objective_text = self.TASKS.get(
            objective,
            self.TASKS[
                "Investigación jurídica"
            ],
        ).strip()
        source_index = self._source_index(
            selected,
            ranked,
        )
        source_blocks = self._source_blocks(
            selected,
            ranked,
            source_char_limit=source_char_limit,
        )
        plan_text = self._render_plan(plan)

        content = f"""Necesito que elabores un informe jurídico profesional sobre la siguiente consulta.

CONSULTA JURÍDICA

{query.strip()}

OBJETIVO

{objective_text}

INDICACIÓN ADICIONAL

{additional_instruction.strip() or "No se agregó una indicación adicional."}

HECHOS DEL CASO

{facts.strip() or "No se suministraron hechos adicionales."}

CRITERIO DE TRABAJO

Trabajá únicamente con las fuentes incluidas debajo.
No agregues hechos, normas, jurisprudencia, doctrina ni argumentos externos.
Toda afirmación jurídica o fáctica debe indicar la fuente correspondiente como [FUENTE N].
Si las fuentes no permiten responder un punto, indicá exactamente qué información falta.
Comenzá directamente con el informe, sin describir este mensaje ni pedir aclaraciones previas.

PLAN DE INVESTIGACIÓN PREPARADO POR LEXIA

{plan_text}

FUENTES

{source_blocks}

ESTRUCTURA DE LA RESPUESTA

1. Conclusión.
2. Encuadre jurídico.
3. Desarrollo de los fundamentos.
4. Aplicación a los hechos.
5. Criterios favorables.
6. Criterios adversos únicamente cuando surjan de las fuentes.
7. Prueba necesaria o faltante.
8. Riesgos procesales sustentados en las fuentes.
9. Estrategia o próximos pasos.
10. Fuentes decisivas.
11. Información insuficiente o pendiente de verificar.
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
            interpretation={
                **interpretation.to_dict(),
                "knowledge_plan": plan.to_dict(),
            },
            document_count=len(candidates),
            selected_count=self._document_source_count(selected),
        )

    def _merge_queries(
        self,
        interpreted,
        planned,
    ):
        output = []
        seen = set()

        for value in [
            *list(interpreted or []),
            *list(planned or []),
        ]:
            clean = " ".join(str(value).split()).strip()
            key = clean.casefold()

            if clean and key not in seen:
                output.append(clean)
                seen.add(key)

            if (
                len(output)
                >= SETTINGS.knowledge_max_search_queries
            ):
                break

        return output

    def _render_plan(self, plan) -> str:
        return "\n".join(
            [
                (
                    "- Conceptos centrales: "
                    + (
                        ", ".join(plan.concepts)
                        or "No determinados"
                    )
                ),
                (
                    "- Conceptos relacionados: "
                    + (
                        ", ".join(
                            plan.related_concepts
                        )
                        or "No determinados"
                    )
                ),
                (
                    "- Tipos documentales: "
                    + ", ".join(
                        plan.required_categories
                    )
                ),
                (
                    "- Autoridades preferidas: "
                    + ", ".join(
                        plan.preferred_authorities
                    )
                ),
                (
                    "- Jurisdicciones: "
                    + (
                        ", ".join(
                            plan.jurisdictions
                        )
                        or "No determinada"
                    )
                ),
                (
                    "- Información faltante: "
                    + (
                        ", ".join(
                            plan.missing_dimensions
                        )
                        or "Ninguna detectada"
                    )
                ),
                (
                    "- Confianza: "
                    f"{plan.confidence:.0%}"
                ),
            ]
        )

    def _source_index(
        self,
        results,
        ranked=None,
    ) -> str:
        notes = {}

        if ranked:
            notes = {
                str(item[1].document_path): (
                    item[2],
                    item[3],
                )
                for item in ranked
            }

        lines = []

        for number, fragments in enumerate(
            self._document_groups(results),
            start=1,
        ):
            first = fragments[0]
            concepts, authority = notes.get(
                str(first.document_path),
                ([], ""),
            )
            reasons = []

            if concepts:
                reasons.append(
                    "conceptos: " + ", ".join(concepts[:5])
                )
            if authority:
                reasons.append("autoridad: " + authority)

            locations = ", ".join(
                dict.fromkeys(fragment.page_label for fragment in fragments)
            )
            suffix = (
                f" ({'; '.join(reasons)})"
                if reasons
                else ""
            )
            lines.append(
                f"- [FUENTE {number}] "
                f"{first.document_name} — "
                f"{first.category} — "
                f"{locations}{suffix}"
            )

        return "\n".join(lines)

    def _source_blocks(
        self,
        results,
        ranked=None,
        source_char_limit=None,
    ) -> str:
        notes = {
            str(item[1].document_path): (
                item[2],
                item[3],
            )
            for item in (ranked or [])
        }
        blocks = []
        total_chars = 0
        per_fragment_limit = int(
            source_char_limit
            or SETTINGS.context_builder_max_chars_per_source
        )

        for number, fragments in enumerate(
            self._document_groups(results),
            start=1,
        ):
            first = fragments[0]
            concepts, authority = notes.get(
                str(first.document_path),
                ([], ""),
            )
            excerpts = []

            for fragment_number, result in enumerate(fragments, start=1):
                text = " ".join(result.text.split())[:per_fragment_limit]
                excerpts.append(
                    f"FRAGMENTO {fragment_number}\n"
                    f"Ubicación: {result.page_label}\n"
                    f"Contenido:\n{text}"
                )

            block = (
                f"[FUENTE {number}]\n"
                f"Documento: {first.document_name}\n"
                f"Categoría: {first.category}\n"
                "Conceptos coincidentes: "
                f"{', '.join(concepts) or 'No determinados'}\n"
                f"Autoridad: "
                f"{authority or 'Sin preferencia especial'}\n"
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

    def _render_sources(self, results) -> str:
        # curate_package usa este método al confirmar las fichas elegidas.
        return self._source_blocks(results, ranked=None)

    def _stage(
        self,
        name,
        **metadata,
    ):
        if not self.performance_profiler:
            return nullcontext()

        return self.performance_profiler.stage(
            name,
            **metadata,
        )
