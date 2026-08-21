from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass

from ai.lm_studio_client import LMStudioClient
from ai.response_guard import SpanishLegalResponseGuard
from config.settings import SETTINGS
from services.intelligence_monitor import (
    IntelligenceMonitor,
    MonitorSnapshot,
    ProgressCallback,
)


@dataclass(slots=True)
class JudgmentChunk:
    index: int
    page_start: int | None
    page_end: int | None
    text: str

    @property
    def page_label(self) -> str:
        if self.page_start is None:
            return "páginas no determinadas"
        if self.page_end in (None, self.page_start):
            return f"página {self.page_start}"
        return f"páginas {self.page_start}-{self.page_end}"


@dataclass(slots=True)
class JurisprudenceAnalysisResult:
    source_name: str
    analysis_type: str
    answer: str
    content_hash: str
    total_pages: int | None
    chunks_analyzed: int
    partial_analyses: list[str]
    monitor: MonitorSnapshot
    cached: bool = False


class JurisprudenceAnalyzer:
    SYSTEM = """SOS LEXIA, ANALISTA DE JURISPRUDENCIA ARGENTINA.

REGLAS ABSOLUTAS:
1. RESPONDÉ EXCLUSIVAMENTE EN ESPAÑOL JURÍDICO ARGENTINO.
2. NO ESCRIBAS TÍTULOS, PÁRRAFOS NI TRADUCCIONES EN INGLÉS.
3. ANALIZÁ ÚNICAMENTE EL TEXTO DEL FALLO SUMINISTRADO.
4. NO INVENTES HECHOS, AGRAVIOS, NORMAS, PRECEDENTES, VOTOS NI DECISIONES.
5. DIFERENCIÁ LO DECIDIDO, LOS ARGUMENTOS DE LAS PARTES Y TU EXPLICACIÓN.
6. CUANDO EL TEXTO NO PERMITA DETERMINAR ALGO, INDICALO EXPRESAMENTE.
7. CONSERVÁ LAS REFERENCIAS DE PÁGINA CON EL FORMATO [PÁGINA N] O [PÁGINAS N-M].
8. NO PRESENTES COMO DOCTRINA CENTRAL UNA MENCIÓN INCIDENTAL.
9. ENTREGÁ UN ANÁLISIS TÉCNICO, CLARO, TRAZABLE Y ÚTIL PARA LITIGAR.
"""

    def __init__(self, repository=None):
        self.client = LMStudioClient()
        self.guard = SpanishLegalResponseGuard(self.client)
        self.repository = repository

    def analyze(
        self,
        text: str,
        source_name: str,
        analysis_type: str = "Ficha jurisprudencial completa",
        source_path: str = "",
        total_pages: int | None = None,
        force: bool = False,
        progress_callback: ProgressCallback | None = None,
    ) -> JurisprudenceAnalysisResult:
        clean_text = text.strip()
        if len(clean_text) < 300:
            raise ValueError(
                "El texto extraído es demasiado breve para analizar el fallo."
            )

        content_hash = hashlib.sha256(
            clean_text.encode("utf-8")
        ).hexdigest()
        monitor = IntelligenceMonitor(
            source_name,
            "Analizador de jurisprudencia",
            progress_callback,
        )

        if self.repository and not force:
            cached = self.repository.find(content_hash, analysis_type)
            if cached:
                monitor.step(
                    "caché",
                    "Se recuperó un análisis previo",
                    98,
                )
                snapshot = monitor.finish(
                    cache=True,
                    páginas=cached.get("pages"),
                    fragmentos=cached.get("chunks", 0),
                )
                return JurisprudenceAnalysisResult(
                    source_name=source_name,
                    analysis_type=analysis_type,
                    answer=cached["analysis_text"],
                    content_hash=content_hash,
                    total_pages=cached.get("pages"),
                    chunks_analyzed=cached.get("chunks", 0),
                    partial_analyses=[],
                    monitor=snapshot,
                    cached=True,
                )

        try:
            monitor.step(
                "preparación",
                "Leyendo y organizando el fallo",
                5,
                caracteres=len(clean_text),
            )
            chunks = self._chunk(clean_text)
            if not chunks:
                raise ValueError("No se pudieron formar fragmentos del fallo.")

            monitor.step(
                "segmentación",
                "Fallo dividido para análisis jerárquico",
                12,
                fragmentos=len(chunks),
                páginas=total_pages or "no determinadas",
            )

            partials: list[str] = []
            for position, chunk in enumerate(chunks, start=1):
                progress = 12 + int(53 * position / len(chunks))
                monitor.step(
                    "análisis_parcial",
                    f"Mistral analiza el fragmento {position} de {len(chunks)}",
                    progress,
                    detail=chunk.page_label,
                    fragmento=position,
                    total_fragmentos=len(chunks),
                )
                partial = self.client.chat(
                    self.SYSTEM + self._partial_structure(),
                    self._partial_prompt(chunk, source_name),
                    max_tokens=SETTINGS.judgment_max_partial_tokens,
                    temperature=0.0,
                )
                partials.append(
                    self.guard.ensure_spanish_only(
                        partial,
                        max_tokens=SETTINGS.judgment_max_partial_tokens,
                    )
                )

            monitor.step(
                "consolidación",
                "Consolidando los análisis parciales",
                70,
                análisis_parciales=len(partials),
            )
            condensed = self._hierarchical_condense(
                partials,
                source_name,
                monitor,
            )

            monitor.step(
                "síntesis_final",
                "Preparando la ficha jurisprudencial definitiva",
                88,
            )
            final = self.client.chat(
                self.SYSTEM + self._final_structure(analysis_type),
                self._final_prompt(source_name, analysis_type, condensed),
                max_tokens=SETTINGS.judgment_final_tokens,
                temperature=0.0,
            )
            final = self.guard.ensure_spanish_only(
                final,
                max_tokens=SETTINGS.judgment_final_tokens,
            )

            monitor.step(
                "control",
                "Controlando idioma, estructura y trazabilidad",
                96,
            )
            if self.repository:
                self.repository.save(
                    content_hash=content_hash,
                    source_name=source_name,
                    source_path=source_path,
                    analysis_type=analysis_type,
                    analysis_text=final,
                    metadata={
                        "modelo": SETTINGS.lm_studio_model,
                        "caracteres": len(clean_text),
                    },
                    pages=total_pages,
                    chunks=len(chunks),
                )

            snapshot = monitor.finish(
                páginas=total_pages or "no determinadas",
                fragmentos=len(chunks),
                caracteres=len(clean_text),
            )
            return JurisprudenceAnalysisResult(
                source_name=source_name,
                analysis_type=analysis_type,
                answer=final,
                content_hash=content_hash,
                total_pages=total_pages,
                chunks_analyzed=len(chunks),
                partial_analyses=partials,
                monitor=snapshot,
            )
        except Exception as error:
            monitor.fail(error)
            raise

    def _chunk(self, text: str) -> list[JudgmentChunk]:
        page_pattern = re.compile(
            r"---\s*PÁGINA\s+(\d+)\s*---",
            flags=re.IGNORECASE,
        )
        matches = list(page_pattern.finditer(text))

        if matches:
            pages: list[tuple[int, str]] = []
            for index, match in enumerate(matches):
                start = match.end()
                end = (
                    matches[index + 1].start()
                    if index + 1 < len(matches)
                    else len(text)
                )
                pages.append(
                    (int(match.group(1)), text[start:end].strip())
                )
            return self._pack_pages(pages)

        return self._pack_plain_text(text)

    def _pack_pages(
        self,
        pages: list[tuple[int, str]],
    ) -> list[JudgmentChunk]:
        chunks: list[JudgmentChunk] = []
        buffer: list[str] = []
        start_page: int | None = None
        end_page: int | None = None
        current_size = 0

        for page_number, page_text in pages[: SETTINGS.judgment_max_pages]:
            page_block = f"[PÁGINA {page_number}]\n{page_text}"
            if (
                buffer
                and current_size + len(page_block)
                > SETTINGS.judgment_chunk_chars
            ):
                chunks.append(
                    JudgmentChunk(
                        len(chunks) + 1,
                        start_page,
                        end_page,
                        "\n\n".join(buffer),
                    )
                )
                overlap = buffer[-1][
                    -SETTINGS.judgment_chunk_overlap_chars:
                ]
                buffer = ["[CONTINUIDAD]\n" + overlap]
                current_size = len(buffer[0])
                start_page = page_number
            if start_page is None:
                start_page = page_number
            end_page = page_number
            buffer.append(page_block)
            current_size += len(page_block)

        if buffer:
            chunks.append(
                JudgmentChunk(
                    len(chunks) + 1,
                    start_page,
                    end_page,
                    "\n\n".join(buffer),
                )
            )
        return chunks

    def _pack_plain_text(self, text: str) -> list[JudgmentChunk]:
        paragraphs = [
            p.strip()
            for p in re.split(r"\n\s*\n", text)
            if p.strip()
        ]
        chunks: list[JudgmentChunk] = []
        buffer: list[str] = []
        size = 0
        for paragraph in paragraphs:
            if (
                buffer
                and size + len(paragraph)
                > SETTINGS.judgment_chunk_chars
            ):
                chunks.append(
                    JudgmentChunk(
                        len(chunks) + 1,
                        None,
                        None,
                        "\n\n".join(buffer),
                    )
                )
                overlap = buffer[-1][
                    -SETTINGS.judgment_chunk_overlap_chars:
                ]
                buffer = [overlap]
                size = len(overlap)
            buffer.append(paragraph)
            size += len(paragraph)
        if buffer:
            chunks.append(
                JudgmentChunk(
                    len(chunks) + 1,
                    None,
                    None,
                    "\n\n".join(buffer),
                )
            )
        return chunks

    def _hierarchical_condense(
        self,
        partials: list[str],
        source_name: str,
        monitor: IntelligenceMonitor,
    ) -> str:
        current = partials
        round_number = 0
        while len("\n\n".join(current)) > 7000 and len(current) > 1:
            round_number += 1
            groups = [
                current[i:i + 4]
                for i in range(0, len(current), 4)
            ]
            next_round: list[str] = []
            for index, group in enumerate(groups, start=1):
                monitor.step(
                    "reducción_jerárquica",
                    f"Consolidando grupo {index} de {len(groups)}",
                    min(86, 72 + round_number * 4 + index),
                )
                prompt = (
                    f"FALLO: {source_name}\n\n"
                    "ANÁLISIS PARCIALES:\n\n"
                    + "\n\n---\n\n".join(group)
                    + "\n\nConsolidá sin perder decisiones, reglas "
                    "jurídicas, argumentos, disidencias ni referencias "
                    "de página."
                )
                summary = self.client.chat(
                    self.SYSTEM,
                    prompt,
                    max_tokens=650,
                    temperature=0.0,
                )
                next_round.append(
                    self.guard.ensure_spanish_only(
                        summary,
                        max_tokens=650,
                    )
                )
            current = next_round
        return "\n\n---\n\n".join(current)

    def _partial_prompt(
        self,
        chunk: JudgmentChunk,
        source_name: str,
    ) -> str:
        return f"""FALLO: {source_name}
FRAGMENTO: {chunk.index} — {chunk.page_label}

TEXTO:
{chunk.text}

TAREA:
Extraé únicamente lo que surge de este fragmento. Identificá hechos,
antecedentes procesales, argumentos, normas, precedentes, fundamentos,
decisiones, votos y citas útiles. Conservá las referencias de página.
No completes información ausente con conocimiento externo.
"""

    def _partial_structure(self) -> str:
        return """
FORMATO DEL ANÁLISIS PARCIAL:
- Contenido relevante del fragmento
- Hechos o antecedentes
- Argumentos de las partes
- Fundamentos del tribunal
- Normas y precedentes mencionados
- Decisiones o conclusiones
- Citas textuales breves útiles
- Información que falta para comprender el fallo completo
"""

    def _final_prompt(
        self,
        source_name: str,
        analysis_type: str,
        condensed: str,
    ) -> str:
        return f"""FALLO: {source_name}
TIPO DE SALIDA: {analysis_type}

ANÁLISIS CONSOLIDADO DE TODO EL FALLO:
{condensed}

TAREA FINAL:
Prepará una ficha exacta, comprensible y útil para un abogado litigante.
No agregues nada que no surja del análisis consolidado. Mantené las
referencias de página disponibles. Si una sección no puede determinarse,
escribí expresamente: "No surge con claridad del texto analizado".
"""

    def _final_structure(self, analysis_type: str) -> str:
        if analysis_type == "Resumen ejecutivo":
            return """
ESTRUCTURA OBLIGATORIA:
1. Identificación del fallo
2. Pregunta jurídica
3. Respuesta del tribunal
4. Fundamentos decisivos
5. Regla jurídica aplicable
6. Utilidad práctica
7. Limitaciones
"""
        if analysis_type == "Explicación sencilla":
            return """
ESTRUCTURA OBLIGATORIA:
1. Qué ocurrió
2. Qué discutían las partes
3. Qué decidió el tribunal
4. Por qué decidió así
5. Qué regla deja el fallo
6. Ejemplo de cuándo podría utilizarse
7. Qué no resuelve el fallo
Usá lenguaje claro sin perder precisión jurídica.
"""
        return """
ESTRUCTURA OBLIGATORIA:
# Ficha jurisprudencial
- Tribunal
- Sala
- Fecha
- Partes
- Expediente
- Tipo de proceso
- Resultado

## Resumen ejecutivo
## Hechos relevantes
## Antecedentes procesales
## Cuestión jurídica central
## Pretensiones y argumentos de las partes
## Normativa aplicada
## Precedentes citados
## Fundamentos del tribunal
## Decisión y alcance
## Ratio decidendi
## Consideraciones incidentales u obiter dicta
## Votos, mayorías y disidencias
## Doctrina o regla jurídica extraíble
## Citas textuales decisivas
## Utilidad práctica para litigación
## Límites y supuestos distinguibles
## Explicación sencilla
## Información que no surge del fallo
"""
