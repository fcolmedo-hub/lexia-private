from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from ai.citation_verifier import CitationCheck, CitationVerifier
from ai.context_builder import LegalContextBuilder, SourcePacket
from ai.language_guard import LanguageCheck, SpanishLanguageGuard
from ai.lm_studio_client import LMStudioClient
from ai.response_guard import SpanishLegalResponseGuard
from models.query_interpretation import QueryInterpretation
from models.search_result import SearchResult
from services.intelligence_monitor import IntelligenceMonitor, MonitorSnapshot, ProgressCallback


@dataclass(slots=True)
class IntelligenceResult:
    answer: str
    mode: str
    interpretation: QueryInterpretation
    sources: list[SourcePacket]
    citation_check: CitationCheck
    language_check: LanguageCheck
    research_queries: list[str] = field(default_factory=list)
    intermediate_notes: list[str] = field(default_factory=list)
    monitor: MonitorSnapshot | None = None


class LexIAIntelligenceCore:
    """Motor local de investigación jurídica por etapas.

    Está diseñado para modelos con contexto pequeño (Mistral 7B / 4096 tokens):
    recupera ampliamente, analiza en lotes y recién luego sintetiza.
    """

    BASE_SYSTEM = """Sos LexIA, un asistente jurídico para un abogado argentino.
REGLAS OBLIGATORIAS:
- RESPONDÉ EXCLUSIVAMENTE EN ESPAÑOL. No incluyas traducciones ni párrafos en inglés.
- Usá únicamente la información suministrada en esta solicitud.
- No inventes fallos, normas, tribunales, fechas, hechos ni citas.
- Toda afirmación jurídica relevante debe citarse como [FUENTE N].
- Si el material no alcanza, decí expresamente: 'Las fuentes recuperadas no permiten sostenerlo'.
- Separá con claridad reglas extraídas, inferencias y recomendaciones.
- No repitas la pregunta ni redactes introducciones genéricas.
"""

    def __init__(self, interpreted_search, interpreter):
        self.interpreted_search = interpreted_search
        self.interpreter = interpreter
        self.client = LMStudioClient()
        self.context_builder = LegalContextBuilder()
        self.verifier = CitationVerifier()
        self.language_guard = SpanishLanguageGuard()
        self.response_guard = SpanishLegalResponseGuard(self.client)

    def deep_research(
        self,
        query: str,
        facts: str = "",
        max_sources: int = 18,
        progress_callback: ProgressCallback | None = None,
    ) -> IntelligenceResult:
        monitor = IntelligenceMonitor(query, "Investigación profunda", progress_callback)
        try:
            monitor.step("interpretación", "Interpretando la consulta", 8)
            interpretation = self.interpreter.interpret(query)
            monitor.step(
                "planificación",
                "Construyendo el plan de investigación",
                16,
                area=interpretation.area,
                instituto=interpretation.main_institute,
                subtemas=len(interpretation.subtopics),
            )
            queries = self._research_queries(interpretation)
            monitor.step(
                "recuperación",
                "Buscando en la biblioteca jurídica",
                28,
                consultas=len(queries),
            )
            results = self._retrieve(queries, max_sources=max_sources)
            monitor.step(
                "selección",
                "Seleccionando y diversificando fuentes",
                42,
                candidatos=len(results),
            )
            packets = self._packets(results, max_sources)
            self._require_sources(packets)
            monitor.step(
                "análisis_lotes",
                "Mistral está analizando las fuentes por lotes",
                52,
                fuentes=len(packets),
                lotes=(len(packets) + 3) // 4,
            )
            batch_notes = self._analyze_batches(
                query, facts, packets, monitor=monitor
            )
            monitor.step(
                "síntesis",
                "Mistral está preparando la síntesis jurídica",
                82,
                análisis_parciales=len(batch_notes),
            )
            synthesis_prompt = self._synthesis_prompt(
                query, facts, interpretation, batch_notes, packets
            )
            answer = self.client.chat(
                self.BASE_SYSTEM + self._research_structure(),
                synthesis_prompt,
                max_tokens=900,
            )
            monitor.step(
                "verificación",
                "Verificando idioma, citas y consistencia",
                93,
            )
            answer = self._review_and_repair(answer, query, packets)
            snapshot = monitor.finish(
                fuentes=len(packets),
                citas=len(self.verifier.verify(answer, len(packets)).cited_numbers),
            )
            return self._result(
                answer, "Investigación profunda", interpretation, packets,
                queries, batch_notes, snapshot
            )
        except Exception as error:
            monitor.fail(error)
            raise

    def contradictions(
        self,
        query: str,
        facts: str = "",
        max_sources: int = 16,
        progress_callback: ProgressCallback | None = None,
    ) -> IntelligenceResult:
        monitor = IntelligenceMonitor(query if "query" in locals() else thesis, "Contradicciones", progress_callback)
        monitor.step("interpretación", "Interpretando la cuestión jurídica", 10)
        interpretation = self.interpreter.interpret(query)
        queries = self._research_queries(interpretation)
        packets = self._packets(
            self._retrieve(queries, max_sources=max_sources), max_sources
        )
        self._require_sources(packets)
        context = self.context_builder.render(packets)
        prompt = f"""PROBLEMA JURÍDICO:
{query}

HECHOS DEL CASO:
{facts or '[No informados]'}

FUENTES:
{context}

TAREA:
Compará los criterios de las fuentes. Identificá coincidencias, contradicciones reales,
diferencias fácticas, diferencias normativas, evolución temporal y fuentes que puedan
distinguirse. No afirmes que existe contradicción si los casos tratan supuestos diferentes.
"""
        answer = self.client.chat(
            self.BASE_SYSTEM + """
ESTRUCTURA OBLIGATORIA:
1. Coincidencias
2. Criterios divergentes
3. Razón de la divergencia
4. Precedentes distinguibles
5. Criterio de mayor autoridad
6. Consecuencia para el caso
7. Información faltante
""",
            prompt,
            max_tokens=850,
        )
        answer = self._review_and_repair(answer, query, packets)
        snapshot = monitor.finish(fuentes=len(packets))
        return self._result(
            answer, "Contradicciones", interpretation, packets, queries, [], snapshot
        )

    def opposing_counsel(
        self,
        thesis: str,
        facts: str,
        evidence: str = "",
        max_sources: int = 14,
        progress_callback: ProgressCallback | None = None,
    ) -> IntelligenceResult:
        monitor = IntelligenceMonitor(query if "query" in locals() else thesis, "Abogado contrario", progress_callback)
        monitor.step("interpretación", "Interpretando la cuestión jurídica", 10)
        interpretation = self.interpreter.interpret(thesis)
        queries = self._research_queries(interpretation)
        packets = self._packets(
            self._retrieve(queries, max_sources=max_sources), max_sources
        )
        self._require_sources(packets)
        prompt = f"""TESIS QUE DEBÉS ATACAR:
{thesis}

HECHOS AFIRMADOS:
{facts or '[No informados]'}

PRUEBA INDICADA:
{evidence or '[No informada]'}

FUENTES RECUPERADAS:
{self.context_builder.render(packets)}

TAREA:
Actuá como la mejor contraparte posible. Atacá la tesis sin inventar hechos.
Priorizá objeciones decisivas y explicá cómo podría responderse a cada una.
"""
        answer = self.client.chat(
            self.BASE_SYSTEM + """
ESTRUCTURA OBLIGATORIA:
1. Teoría contraria principal
2. Objeciones jurídicas
3. Objeciones fácticas
4. Prueba insuficiente o vulnerable
5. Cuestiones procesales
6. Fuentes adversas
7. Preguntas que formularía la contraparte
8. Cómo fortalecer el caso
""",
            prompt,
            max_tokens=900,
        )
        answer = self._review_and_repair(answer, thesis, packets)
        snapshot = monitor.finish(fuentes=len(packets))
        return self._result(
            answer, "Abogado contrario", interpretation, packets, queries, [], snapshot
        )

    def argument_graph(
        self,
        thesis: str,
        facts: str,
        evidence: str = "",
        max_sources: int = 12,
        progress_callback: ProgressCallback | None = None,
    ) -> IntelligenceResult:
        monitor = IntelligenceMonitor(query if "query" in locals() else thesis, "Grafo argumental", progress_callback)
        monitor.step("interpretación", "Interpretando la cuestión jurídica", 10)
        interpretation = self.interpreter.interpret(thesis)
        queries = self._research_queries(interpretation)
        packets = self._packets(
            self._retrieve(queries, max_sources=max_sources), max_sources
        )
        self._require_sources(packets)
        prompt = f"""TESIS:
{thesis}

HECHOS:
{facts or '[No informados]'}

PRUEBA:
{evidence or '[No informada]'}

FUENTES:
{self.context_builder.render(packets)}

Construí un mapa argumental. Cada argumento debe vincular tesis, regla,
fuente, hecho, prueba, inferencia, contraargumento y respuesta.
"""
        answer = self.client.chat(
            self.BASE_SYSTEM + """
FORMATO OBLIGATORIO:
# Tesis central
## Argumento 1
- Regla jurídica:
- Fuente:
- Hecho relevante:
- Prueba:
- Inferencia:
- Contraargumento:
- Respuesta:
- Fortaleza: Alta/Media/Baja
Repetí la estructura para los argumentos necesarios y cerrá con lagunas críticas.
""",
            prompt,
            max_tokens=950,
        )
        answer = self._review_and_repair(answer, thesis, packets)
        snapshot = monitor.finish(fuentes=len(packets))
        return self._result(
            answer, "Grafo argumental", interpretation, packets, queries, [], snapshot
        )

    def draft_section(
        self,
        section: str,
        thesis: str,
        facts: str,
        style_sample: str = "",
        max_sources: int = 10,
        progress_callback: ProgressCallback | None = None,
    ) -> IntelligenceResult:
        monitor = IntelligenceMonitor(query if "query" in locals() else thesis, "Redacción basada en evidencia", progress_callback)
        monitor.step("interpretación", "Interpretando la cuestión jurídica", 10)
        interpretation = self.interpreter.interpret(thesis)
        queries = self._research_queries(interpretation)
        packets = self._packets(
            self._retrieve(queries, max_sources=max_sources), max_sources
        )
        self._require_sources(packets)
        prompt = f"""SECCIÓN A REDACTAR:
{section}

TESIS:
{thesis}

HECHOS AUTORIZADOS:
{facts or '[No informados]'}

MUESTRA DE ESTILO DEL USUARIO:
{style_sample[:1800] or '[No suministrada]'}

FUENTES:
{self.context_builder.render(packets)}

Redactá exclusivamente esta sección. No agregues hechos. Usá citas [FUENTE N]
y señalá entre corchetes cualquier dato o prueba que deba completarse.
"""
        answer = self.client.chat(
            self.BASE_SYSTEM + """
La salida debe ser texto jurídico utilizable, sin comentarios preliminares.
Al final agregá únicamente:
## Control de respaldo
- Afirmaciones que requieren prueba
- Información faltante
- Fuentes utilizadas
""",
            prompt,
            max_tokens=1000,
        )
        answer = self._review_and_repair(answer, thesis, packets)
        snapshot = monitor.finish(fuentes=len(packets))
        return self._result(
            answer, "Redacción basada en evidencia", interpretation,
            packets, queries, [], snapshot
        )

    def _research_queries(
        self, interpretation: QueryInterpretation
    ) -> list[str]:
        queries = [interpretation.original_query]
        queries.extend(interpretation.search_queries)
        for topic in interpretation.subtopics:
            queries.append(
                f"{interpretation.main_institute} {topic}".strip()
            )
        return list(dict.fromkeys(q.strip() for q in queries if q.strip()))[:10]

    def _retrieve(
        self, queries: list[str], max_sources: int
    ) -> list[SearchResult]:
        collected: dict[tuple[str, int], SearchResult] = {}
        scores: dict[tuple[str, int], float] = {}

        for query_index, query in enumerate(queries):
            interpretation = self.interpreter.interpret(query)
            results = self.interpreted_search.search(
                interpretation,
                limit=min(12, max_sources),
            )
            weight = max(0.45, 1.0 - query_index * 0.07)
            for rank, result in enumerate(results, start=1):
                key = (str(Path(result.document_path).resolve()), result.fragment_index)
                score = weight * (float(result.score) + 1.0 / (25 + rank))
                scores[key] = scores.get(key, 0.0) + score
                collected.setdefault(key, result)

        ranked = sorted(
            collected.items(), key=lambda item: scores[item[0]], reverse=True
        )
        # Diversidad documental: máximo dos fragmentos por documento.
        output: list[SearchResult] = []
        per_document: dict[str, int] = {}
        for key, result in ranked:
            document = key[0]
            if per_document.get(document, 0) >= 2:
                continue
            result.score = scores[key]
            output.append(result)
            per_document[document] = per_document.get(document, 0) + 1
            if len(output) >= max_sources:
                break
        return output

    def _packets(
        self, results: list[SearchResult], max_sources: int
    ) -> list[SourcePacket]:
        # El builder limita cada lote; para investigación profunda se construyen
        # paquetes en ventanas sucesivas, preservando numeración global.
        packets: list[SourcePacket] = []
        for result in results[:max_sources]:
            metadata = result.metadata or {}
            label = (
                f"{result.document_name} | {result.category} | "
                f"{result.page_label} | Tribunal: "
                f"{metadata.get('court', 'No detectado')} | Fecha: "
                f"{metadata.get('date', 'No detectada')}"
            )
            text = " ".join(result.text.split())[:900]
            packets.append(SourcePacket(len(packets) + 1, label, text, result))
        return packets

    def _analyze_batches(
        self,
        query: str,
        facts: str,
        packets: list[SourcePacket],
        monitor: IntelligenceMonitor | None = None,
    ) -> list[str]:
        notes: list[str] = []
        total_batches = max(1, (len(packets) + 3) // 4)
        for batch_index, start in enumerate(range(0, len(packets), 4), start=1):
            batch = packets[start:start + 4]
            if monitor:
                progress = 52 + int((batch_index - 1) / total_batches * 26)
                monitor.step(
                    "análisis_lotes",
                    f"Analizando lote {batch_index} de {total_batches}",
                    progress,
                    lote_actual=batch_index,
                    lotes=total_batches,
                    fuentes_analizadas=min(start + len(batch), len(packets)),
                )
            context = self.context_builder.render(batch)
            prompt = f"""PROBLEMA:
{query}

HECHOS:
{facts or '[No informados]'}

LOTE DE FUENTES:
{context}

Extraé sólo hallazgos útiles para responder el problema: regla, aplicación,
criterio favorable, criterio adverso, requisitos, prueba y limitaciones.
Conservá exactamente la numeración [FUENTE N].
"""
            note = self.client.chat(
                self.BASE_SYSTEM + "Respondé en viñetas concisas.",
                prompt,
                max_tokens=380,
            )
            note = self._ensure_spanish(note)
            notes.append(note)
        return notes

    def _synthesis_prompt(
        self,
        query: str,
        facts: str,
        interpretation: QueryInterpretation,
        notes: list[str],
        packets: list[SourcePacket],
    ) -> str:
        notes_text = "\n\n".join(
            f"### ANÁLISIS PARCIAL {index}\n{note}"
            for index, note in enumerate(notes, start=1)
        )
        source_index = "\n".join(
            f"[FUENTE {p.number}] {p.label}" for p in packets
        )
        return f"""PROBLEMA JURÍDICO:
{query}

HECHOS:
{facts or '[No informados]'}

INTERPRETACIÓN:
Área: {interpretation.area}
Instituto: {interpretation.main_institute}
Pretensión: {interpretation.claim_or_goal}
Jurisdicción: {interpretation.jurisdiction}
Subtemas: {', '.join(interpretation.subtopics) or 'No determinados'}

HALLAZGOS DE LOS LOTES:
{notes_text}

ÍNDICE DE FUENTES DISPONIBLES:
{source_index}

Sintetizá sin incorporar conocimiento externo. No cites una fuente si el
hallazgo parcial no la respalda.
"""

    def _research_structure(self) -> str:
        return """
ESTRUCTURA OBLIGATORIA:
1. Conclusión fundada
2. Regla jurídica aplicable
3. Aplicación a los hechos
4. Argumentos favorables
5. Criterios adversos y distinciones
6. Prueba necesaria
7. Riesgos procesales
8. Fuentes decisivas
9. Información faltante
"""

    def _review_and_repair(
        self, answer: str, query: str, packets: list[SourcePacket]
    ) -> str:
        guarded = self.response_guard.enforce(
            answer=answer,
            source_count=len(packets),
            original_query=query,
            max_tokens=850,
        )
        return guarded.text

    def _ensure_spanish(self, text: str) -> str:
        return self.response_guard.ensure_spanish_only(
            text,
            max_tokens=420,
        )

    def _result(
        self,
        answer: str,
        mode: str,
        interpretation: QueryInterpretation,
        packets: list[SourcePacket],
        queries: list[str],
        notes: list[str],
        monitor: MonitorSnapshot | None = None,
    ) -> IntelligenceResult:
        answer = self.verifier.normalize(answer)
        return IntelligenceResult(
            answer=answer,
            mode=mode,
            interpretation=interpretation,
            sources=packets,
            citation_check=self.verifier.verify(answer, len(packets)),
            language_check=self.language_guard.check(answer),
            research_queries=queries,
            intermediate_notes=notes,
            monitor=monitor,
        )

    def _require_sources(self, packets: list[SourcePacket]) -> None:
        if not packets:
            raise RuntimeError(
                "LexIA no recuperó fuentes suficientes. Reformulá la consulta "
                "o incorporá documentación específica a la biblioteca."
            )
