from __future__ import annotations

import math
import re
import sqlite3
import unicodedata
from datetime import datetime
from pathlib import Path
from types import MethodType

from qdrant_client import models

from ai.context_package_builder import ContextPackage
from config.settings import SETTINGS


THEMATIC_TYPES = {"libro", "doctrina", "legislacion"}
STOPWORDS = {
    "a", "al", "algo", "como", "con", "contra", "de", "del", "desde",
    "el", "ella", "en", "entre", "es", "esta", "este", "la", "las",
    "lo", "los", "o", "para", "por", "que", "se", "sin", "sobre", "su",
    "sus", "un", "una", "y",
}


def _fold(value: str) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.casefold()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return " ".join(text.split())


def _type_key(value: str) -> str:
    return _fold(value).replace(" ", "")


def _meaningful_terms(query: str) -> list[str]:
    terms = []
    seen = set()
    for term in _fold(query).split():
        if term in STOPWORDS or len(term) < 2 or term in seen:
            continue
        seen.add(term)
        terms.append(term)
    return terms


def _query_variants(builder, instruction: str) -> list[str]:
    output = []
    seen = set()

    def add(value):
        clean = " ".join(str(value or "").split()).strip()
        key = clean.casefold()
        if clean and key not in seen and len(output) < 5:
            seen.add(key)
            output.append(clean)

    add(instruction)
    try:
        interpreted = builder.interpreter.interpret(instruction)
        for value in list(getattr(interpreted, "search_queries", []) or []):
            add(value)
    except Exception:
        pass

    try:
        expanded = builder.query_expander.expand(
            instruction,
            output,
            max_queries=5,
        )
        for value in expanded:
            add(value)
    except Exception:
        pass

    return output or [instruction]


def _load_document(catalog, requested_path: Path):
    resolved = str(requested_path.expanduser().resolve())
    con = sqlite3.connect(str(catalog.database_path), timeout=10)
    con.row_factory = sqlite3.Row
    try:
        row = con.execute(
            "SELECT path,name,category,total_pages,extraction_method "
            "FROM documents WHERE path IN (?,?) AND COALESCE(is_deleted,0)=0 "
            "ORDER BY CASE WHEN path=? THEN 0 ELSE 1 END LIMIT 1",
            (str(requested_path), resolved, resolved),
        ).fetchone()
        if row is None:
            raise FileNotFoundError(
                "El documento no está disponible en el catálogo activo de LexIA."
            )

        canonical_path = str(row["path"])
        fragments = con.execute(
            "SELECT fragment_index,text_content,start_char,end_char,page_start,page_end "
            "FROM fragments WHERE document_path=? ORDER BY fragment_index",
            (canonical_path,),
        ).fetchall()
    finally:
        con.close()

    if not fragments:
        raise RuntimeError(
            "Este documento todavía no tiene fragmentos indexados. "
            "Reprocesalo antes de usar la búsqueda temática."
        )

    return {
        "path": canonical_path,
        "name": str(row["name"] or requested_path.name),
        "category": str(row["category"] or ""),
        "pages": row["total_pages"],
        "method": str(row["extraction_method"] or "native"),
        "fragments": [dict(item) for item in fragments],
    }


def _lexical_scores(fragments, query: str) -> dict[int, float]:
    query_norm = _fold(query)
    terms = _meaningful_terms(query)
    if not terms:
        return {}

    scores = {}
    for fragment in fragments:
        text = _fold(fragment["text_content"])
        if not text:
            continue
        matched = [term for term in terms if term in text]
        if not matched:
            continue
        coverage = len(matched) / len(terms)
        occurrences = sum(min(text.count(term), 6) for term in matched)
        frequency = min(1.0, math.log1p(occurrences) / math.log(8))
        phrase = 1.0 if query_norm and query_norm in text else 0.0
        score = min(1.0, 0.62 * coverage + 0.18 * frequency + 0.20 * phrase)
        scores[int(fragment["fragment_index"])] = score
    return scores


def _semantic_scores(vector_store, document_path: str, queries: list[str]) -> dict[int, float]:
    scores = {}
    path_value = str(Path(document_path).expanduser().resolve())

    try:
        for position, query in enumerate(queries):
            weight = max(0.70, 1.0 - position * 0.08)
            response = vector_store.client.query_points(
                collection_name=vector_store.collection_name,
                query=vector_store.embedding_service.embed_query(query).tolist(),
                query_filter=models.Filter(
                    must=[
                        models.FieldCondition(
                            key="document_path",
                            match=models.MatchValue(value=path_value),
                        )
                    ]
                ),
                limit=64,
                with_payload=True,
            )
            for point in response.points:
                payload = point.payload or {}
                index = int(payload.get("fragment_index", 0) or 0)
                score = max(0.0, min(1.0, float(point.score or 0.0))) * weight
                scores[index] = max(scores.get(index, 0.0), score)
    except Exception:
        # Si Qdrant no está disponible, la búsqueda textual sigue siendo útil
        # y evita convertir una incidencia del índice vectorial en pérdida total.
        return {}

    return scores


def _rank_fragments(fragments, instruction: str, semantic: dict[int, float]):
    lexical = _lexical_scores(fragments, instruction)
    by_index = {int(item["fragment_index"]): item for item in fragments}
    ranked = []

    for index in set(lexical) | set(semantic):
        lex = lexical.get(index, 0.0)
        sem = semantic.get(index, 0.0)
        combined = 0.55 * sem + 0.45 * lex
        if lex >= 0.80:
            combined += 0.06
        ranked.append((min(1.0, combined), index))

    ranked.sort(reverse=True)
    if not ranked:
        return [], by_index, lexical

    best = ranked[0][0]
    threshold = max(0.24, best * 0.52)
    seeds = [(score, index) for score, index in ranked if score >= threshold][:18]
    return seeds, by_index, lexical


def _selected_regions(seeds, by_index, lexical):
    if not seeds:
        return []

    available = set(by_index)
    selected = set()
    seed_scores = {index: score for score, index in seeds}

    for score, index in seeds:
        selected.add(index)
        for neighbor in (index - 1, index + 1):
            if neighbor in available:
                selected.add(neighbor)
        for neighbor in (index - 2, index + 2):
            if neighbor in available and lexical.get(neighbor, 0.0) >= 0.28:
                selected.add(neighbor)

    ordered = sorted(selected)
    groups = []
    current = [ordered[0]]
    for index in ordered[1:]:
        gap = index - current[-1]
        if gap <= 3:
            for missing in range(current[-1] + 1, index):
                if missing in available:
                    current.append(missing)
            current.append(index)
        else:
            groups.append(current)
            current = [index]
    groups.append(current)

    regions = []
    for indices in groups:
        score = max(seed_scores.get(index, 0.0) for index in indices)
        pages = []
        for index in indices:
            fragment = by_index[index]
            for value in (fragment.get("page_start"), fragment.get("page_end")):
                if value is not None:
                    try:
                        pages.append(int(value))
                    except (TypeError, ValueError):
                        pass
        regions.append(
            {
                "indices": indices,
                "score": score,
                "page_start": min(pages) if pages else None,
                "page_end": max(pages) if pages else None,
            }
        )

    return regions


def _merge_texts(texts: list[str]) -> str:
    merged = ""
    for raw in texts:
        text = str(raw or "").strip()
        if not text:
            continue
        if not merged:
            merged = text
            continue
        overlap = 0
        maximum = min(400, len(merged), len(text))
        for size in range(maximum, 39, -1):
            if merged[-size:] == text[:size]:
                overlap = size
                break
        addition = text[overlap:].lstrip()
        if addition:
            merged += "\n\n" + addition
    return merged


def _page_label(region) -> str:
    start = region.get("page_start")
    end = region.get("page_end")
    if start and end and start != end:
        return f"Páginas {start}-{end}"
    if start or end:
        return f"Página {start or end}"
    return "Ubicación no determinada"


def _build_thematic_package(builder, catalog, vector_store, documents, objective, instruction, document_type):
    instruction = str(instruction or "").strip()
    if not instruction:
        raise ValueError(
            "Ingresá Indicaciones para señalar qué tema debe buscar LexIA dentro del documento."
        )

    items = list(documents or [])
    if len(items) != 1:
        raise ValueError(
            "La búsqueda temática de Libro, Doctrina o Legislación requiere un documento por vez."
        )

    raw = items[0]
    path = Path(raw[0] if isinstance(raw, (tuple, list)) else raw)
    document = _load_document(catalog, path)
    variants = _query_variants(builder, instruction)
    semantic = _semantic_scores(vector_store, document["path"], variants)
    seeds, by_index, lexical = _rank_fragments(
        document["fragments"], instruction, semantic
    )
    regions = _selected_regions(seeds, by_index, lexical)

    if not regions:
        raise RuntimeError(
            "LexIA no encontró pasajes suficientemente relacionados con las Indicaciones "
            "dentro de este documento."
        )

    max_total = int(SETTINGS.context_builder_max_total_chars)
    reserved = min(14000, max(6000, int(max_total * 0.10)))
    source_budget = max(12000, max_total - reserved)

    # Elegimos primero por relevancia. Una zona extensa y coherente puede ocupar
    # la mayor parte del presupuesto: no se fuerza diversidad artificial cuando
    # el tema está concentrado en un solo capítulo del libro.
    chosen = []
    used = 0
    for region in sorted(regions, key=lambda item: item["score"], reverse=True):
        text = _merge_texts(
            [by_index[index]["text_content"] for index in region["indices"]]
        )
        if not text:
            continue
        remaining = source_budget - used
        if remaining <= 1200:
            break
        if len(text) > remaining:
            text = text[:remaining].rsplit(" ", 1)[0].rstrip()
            text += "\n\n[CORTE POR LÍMITE DEL PAQUETE]"
        chosen.append({**region, "text": text})
        used += len(text)
        if used >= source_budget or len(chosen) >= 12:
            break

    if not chosen:
        raise RuntimeError("Los pasajes encontrados no pudieron incorporarse al paquete.")

    # Para leerlo como un libro, una vez elegidas las zonas pertinentes se
    # presentan en el orden en que aparecen en el documento.
    chosen.sort(
        key=lambda item: (
            item.get("page_start") is None,
            item.get("page_start") or item["indices"][0],
        )
    )

    source_blocks = []
    source_index = []
    for number, region in enumerate(chosen, start=1):
        location = _page_label(region)
        source_index.append(f"- [FUENTE {number}] {location}")
        source_blocks.append(
            f"[FUENTE {number}]\n"
            f"Documento: {document['name']}\n"
            f"Tipo indicado: {document_type}\n"
            f"Ubicación: {location}\n"
            f"Pertinencia estimada por LexIA: {region['score']:.0%}\n"
            f"Ruta local: {document['path']}\n"
            f"Contenido:\n{region['text']}"
        )

    created_at = datetime.now().isoformat(timespec="seconds")
    objective_text = builder.TASKS.get(
        objective,
        builder.TASKS["Investigación jurídica"],
    ).strip()
    variants_text = "\n".join(f"- {query}" for query in variants)

    content = f"""# LEXIA — ESTUDIO TEMÁTICO DE DOCUMENTO

## DOCUMENTO

- Nombre: {document['name']}
- Tipo indicado: {document_type}
- Categoría: {document['category'] or 'Sin categoría'}
- Páginas detectadas: {document['pages'] or 'No determinadas'}
- Método de extracción: {document['method']}

## INDICACIONES

{instruction}

## CRITERIO DE RECUPERACIÓN

LexIA examinó los fragmentos indexados a lo largo de todo el documento y seleccionó
las zonas relacionadas con las Indicaciones. Los pasajes no pertinentes fueron descartados.
Las zonas vecinas se conservaron cuando aportaban continuidad de lectura y contexto.

Consultas de recuperación utilizadas:
{variants_text}

## PASAJES SELECCIONADOS

{chr(10).join(source_index)}

## TAREA PARA CHATGPT

{objective_text}

Trabajá únicamente con los pasajes incluidos debajo. No supongas que el resto del libro,
doctrina o legislación sostiene una conclusión que no aparezca en estas fuentes. Citá cada
afirmación relevante como [FUENTE N] e indicá la página cuando esté disponible.

## FUENTES

{chr(10).join(chr(10) + block for block in source_blocks)}

## CONTROL FINAL

Respondé directamente en español. Concentrá el análisis en el tema indicado por el usuario.
Si los pasajes seleccionados no permiten responder algún aspecto, señalalo expresamente.
"""

    return ContextPackage(
        title="Estudio_tematico_" + builder._safe_title(Path(document["name"]).stem),
        content=content,
        sources=[],
        created_at=created_at,
        character_count=len(content),
        objective=objective,
        query=instruction,
        facts="",
        interpretation={
            "document_type": document_type,
            "document": document["name"],
            "queries": variants,
            "regions_selected": len(chosen),
            "semantic_available": bool(semantic),
            "pages": document["pages"],
        },
        document_count=1,
        selected_count=len(chosen),
    )


def install_thematic_document_study(builder, catalog, vector_store) -> None:
    """Activa estudio temático solo para Libro, Doctrina y Legislación."""
    if getattr(builder, "_lexia_thematic_study_installed", False):
        return

    original = builder.build_documents_package

    def wrapped(
        self,
        documents,
        objective: str = "Análisis de jurisprudencia",
        instruction: str = "",
        document_type: str = "Detección automática",
    ):
        if _type_key(document_type) not in THEMATIC_TYPES:
            return original(
                documents=documents,
                objective=objective,
                instruction=instruction,
                document_type=document_type,
            )
        return _build_thematic_package(
            self,
            catalog,
            vector_store,
            documents,
            objective,
            instruction,
            document_type,
        )

    builder.build_documents_package = MethodType(wrapped, builder)
    builder._lexia_thematic_study_installed = True
