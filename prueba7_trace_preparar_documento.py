#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LexIA — Prueba 7: trazado de consultas de Preparar documento

Objetivo:
- Obtener exactamente las search_queries que genera Context Builder.
- Medir cada consulta profesional por separado.
- Desglosar cada consulta en FTS / nombre / vector cuando sea posible.

No modifica código de LexIA.
Usa feedback/historial/cache temporales.
Catálogo y Qdrant se usan para consulta.
"""

from __future__ import annotations

import argparse
import inspect
import shutil
import statistics
import sys
import time
from pathlib import Path

DEFAULT_QUERY = "solve et repete"
RUNS = 1


def count_results(value):
    try:
        return len(value)
    except Exception:
        return -1


class Recorder:
    def __init__(self):
        self.events = []

    def clear(self):
        self.events.clear()

    def add(self, layer, query, limit, ms, count):
        self.events.append({
            "layer": layer,
            "query": query,
            "limit": limit,
            "ms": ms,
            "count": count,
        })

    def total(self, layer):
        return sum(e["ms"] for e in self.events if e["layer"] == layer)

    def calls(self, layer):
        return [e for e in self.events if e["layer"] == layer]


def instrument(obj, method_name, recorder, layer):
    if obj is None or not hasattr(obj, method_name):
        return False

    original = getattr(obj, method_name)

    def wrapped(*args, **kwargs):
        query = kwargs.get("query")
        limit = kwargs.get("limit")

        if query is None and args:
            query = args[0]
        if limit is None and len(args) > 1:
            limit = args[1]

        t0 = time.perf_counter()
        result = None
        try:
            result = original(*args, **kwargs)
            return result
        finally:
            recorder.add(
                layer,
                query,
                limit,
                (time.perf_counter() - t0) * 1000,
                count_results(result),
            )

    setattr(obj, method_name, wrapped)
    return True


def call_search(engine, query, limit):
    sig = inspect.signature(engine.search)
    kwargs = {}
    if "limit" in sig.parameters:
        kwargs["limit"] = limit
    if "category" in sig.parameters:
        kwargs["category"] = None
    return engine.search(query, **kwargs)


def merge_queries(builder, a, b):
    if hasattr(builder, "_merge_queries"):
        return list(builder._merge_queries(a, b))

    out = []
    seen = set()
    for q in list(a or []) + list(b or []):
        clean = str(q or "").strip()
        key = clean.casefold()
        if clean and key not in seen:
            seen.add(key)
            out.append(clean)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("root", nargs="?", default=r"D:\LexIA_2.3_DEV")
    ap.add_argument("--query", default=DEFAULT_QUERY)
    args = ap.parse_args()

    root = Path(args.root).resolve()
    query = str(args.query).strip()

    if not query:
        raise SystemExit("La consulta no puede estar vacía.")

    sys.path.insert(0, str(root))

    exp = root / "runtime" / "experiments" / "prepare_document_trace"
    if exp.exists():
        shutil.rmtree(exp)
    exp.mkdir(parents=True, exist_ok=True)

    from config.settings import SETTINGS
    from storage.catalog import DocumentCatalog
    from storage.search_feedback_repository import SearchFeedbackRepository
    from storage.search_history_repository import SearchHistoryRepository
    from search.embedding_service import EmbeddingService
    from search.vector_store import VectorStore
    from search.professional_search import ProfessionalLegalSearchEngine

    try:
        from search.search_hotfix import SearchHotfixEngine
    except Exception:
        SearchHotfixEngine = None

    from services.application import LexIAApplication

    print("=" * 112)
    print("LEXIA — PRUEBA 7: TRACE PREPARAR DOCUMENTO")
    print("=" * 112)
    print(f"Consulta original: {query}")
    print()

    # Usamos la aplicación sólo para reproducir interpretación + Knowledge Plan.
    app = LexIAApplication()
    builder = app.context_builder

    t0 = time.perf_counter()
    interpretation = builder.interpreter.interpret(query)
    interpret_ms = (time.perf_counter() - t0) * 1000

    t0 = time.perf_counter()
    plan = builder.knowledge.plan(query, interpretation)
    plan_ms = (time.perf_counter() - t0) * 1000

    interpreter_queries = list(getattr(interpretation, "search_queries", []) or [])
    plan_queries = list(getattr(plan, "search_queries", []) or [])
    merged = merge_queries(builder, interpreter_queries, plan_queries)

    max_sources = getattr(SETTINGS, "context_builder_max_sources", 10)
    runtime_max = getattr(SETTINGS, "context_builder_runtime_max_sources", max_sources)
    selected_limit = min(max_sources, runtime_max)

    max_candidates = getattr(SETTINGS, "context_builder_max_candidates", 100)
    multiplier = getattr(SETTINGS, "knowledge_candidate_multiplier", 4)
    candidate_limit = min(
        max_candidates,
        max(selected_limit * multiplier, selected_limit),
    )

    print(f"Interpretación: {interpret_ms:.2f} ms")
    print(f"Knowledge Plan: {plan_ms:.2f} ms")
    print(f"candidate_limit reproducido: {candidate_limit}")
    print()

    print("CONSULTAS DEL INTÉRPRETE")
    if interpreter_queries:
        for i, q in enumerate(interpreter_queries, 1):
            print(f"  I{i}. {q}")
    else:
        print("  [ninguna]")
    print()

    print("CONSULTAS DEL KNOWLEDGE PLAN")
    if plan_queries:
        for i, q in enumerate(plan_queries, 1):
            print(f"  K{i}. {q}")
    else:
        print("  [ninguna]")
    print()

    print("CONSULTAS FINALES FUSIONADAS")
    for i, q in enumerate(merged, 1):
        print(f"  Q{i}. {q}")
    print(f"Total: {len(merged)}")
    print()

    # Stack de búsqueda aislado con repositorios accesorios temporales.
    catalog = DocumentCatalog(SETTINGS.catalog_path)
    feedback = SearchFeedbackRepository(exp / "feedback.sqlite3")
    history = SearchHistoryRepository(exp / "history.sqlite3")
    embeddings = EmbeddingService()
    vector = VectorStore(embeddings)

    professional = ProfessionalLegalSearchEngine(
        vector,
        catalog,
        feedback,
        history,
    )

    raw = (
        SearchHotfixEngine(professional, catalog)
        if SearchHotfixEngine is not None
        else professional
    )

    recorder = Recorder()
    instrument(catalog, "lexical_search", recorder, "FTS")
    instrument(catalog, "direct_document_search", recorder, "NOMBRE")
    instrument(vector, "search", recorder, "VECTOR")

    print("Warm-up...")
    embeddings.embed_query("prueba")
    vector.search("prueba", limit=3)
    print("Warm-up OK")
    print()

    print("=" * 112)
    print("TIEMPO POR CONSULTA PROFESIONAL")
    print("=" * 112)

    total_all = 0.0
    reports = []

    for i, q in enumerate(merged, 1):
        recorder.clear()

        t0 = time.perf_counter()
        try:
            results = call_search(raw, q, candidate_limit)
            error = None
        except Exception as exc:
            results = []
            error = str(exc)
        total_ms = (time.perf_counter() - t0) * 1000
        total_all += total_ms

        fts = recorder.total("FTS")
        name = recorder.total("NOMBRE")
        vec = recorder.total("VECTOR")
        accounted = fts + name + vec
        rest = max(0.0, total_ms - accounted)

        report = {
            "index": i,
            "query": q,
            "total_ms": total_ms,
            "fts_ms": fts,
            "name_ms": name,
            "vector_ms": vec,
            "rest_ms": rest,
            "results": count_results(results),
            "error": error,
        }
        reports.append(report)

        print(f"Q{i}: {q}")
        print(f"  TOTAL:       {total_ms:10.2f} ms")
        print(f"  FTS acum.:   {fts:10.2f} ms  ({len(recorder.calls('FTS'))} llamadas)")
        print(f"  NOMBRE:      {name:10.2f} ms  ({len(recorder.calls('NOMBRE'))} llamadas)")
        print(f"  VECTOR:      {vec:10.2f} ms  ({len(recorder.calls('VECTOR'))} llamadas)")
        print(f"  RESTO aprox: {rest:10.2f} ms")
        print(f"  resultados:  {count_results(results)}")

        if error:
            print(f"  ERROR: {error}")

        fts_calls = recorder.calls("FTS")
        if fts_calls:
            print("  Detalle FTS:")
            for n, e in enumerate(fts_calls, 1):
                print(
                    f"    {n:02d}. {e['ms']:9.2f} ms"
                    f" | limit={e['limit']}"
                    f" | res={e['count']}"
                    f" | {e['query']}"
                )

        vec_calls = recorder.calls("VECTOR")
        if vec_calls:
            print("  Detalle VECTOR:")
            for n, e in enumerate(vec_calls, 1):
                print(
                    f"    {n:02d}. {e['ms']:9.2f} ms"
                    f" | limit={e['limit']}"
                    f" | res={e['count']}"
                    f" | {e['query']}"
                )
        print()

    print("-" * 112)
    print(f"SUMA DE LAS {len(merged)} BÚSQUEDAS: {total_all/1000:.3f} s")
    print()

    if reports:
        ordered = sorted(reports, key=lambda x: x["total_ms"], reverse=True)
        print("RANKING DE COSTO")
        for pos, r in enumerate(ordered, 1):
            pct = (r["total_ms"] / total_all * 100) if total_all else 0
            print(
                f"  {pos}. Q{r['index']} — {r['total_ms']/1000:.3f} s"
                f" ({pct:.1f}%) — {r['query']}"
            )

    print()
    print("VERIFICACIÓN")
    print("  Código LexIA modificado:              NO")
    print("  Catálogo de producción modificado:    NO")
    print("  Qdrant modificado:                    NO")
    print("  Feedback/historial usados:            TEMPORALES")
    print(f"  Temporales: {exp}")
    print()
    print("FIN")


if __name__ == "__main__":
    main()
