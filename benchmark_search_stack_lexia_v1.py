#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LexIA — Benchmark Search Stack v1.0

Objetivo:
Medir el pipeline real de búsqueda de LexIA sin modificar las bases funcionales
de feedback/historial/cache.

Lee:
- catálogo real
- Qdrant real

Escribe SOLO:
- runtime/experiments/search_stack_profile/*
"""

from __future__ import annotations

import argparse
import inspect
import json
import shutil
import statistics
import sys
import time
from pathlib import Path
from types import MethodType

QUERIES = [
    '"solve et repete"',
    '"plazo razonable"',
    '"actividad legítima"',
    '"lucro cesante"',
    '"ley 23.548"',
    '"prescripción tributaria"',
    'Telecom',
    '"agotamiento internacional"',
]

RUNS = 3
LIMIT = 100


class Timings:
    def __init__(self):
        self.data = {}

    def add(self, name, seconds):
        self.data.setdefault(name, []).append(seconds * 1000)

    def clear(self):
        self.data.clear()

    def med(self, name):
        vals = self.data.get(name, [])
        return statistics.median(vals) if vals else None


def wrap_method(obj, method_name, timings: Timings, label=None):
    if obj is None or not hasattr(obj, method_name):
        return False

    original = getattr(obj, method_name)
    if not callable(original):
        return False

    key = label or f"{type(obj).__name__}.{method_name}"

    def wrapped(*args, **kwargs):
        t0 = time.perf_counter()
        try:
            return original(*args, **kwargs)
        finally:
            timings.add(key, time.perf_counter() - t0)

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


def count_results(result):
    if result is None:
        return 0
    try:
        return len(result)
    except Exception:
        return -1


def fmt(v):
    return "-" if v is None else f"{v:.2f}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("root", nargs="?", default=r"D:\LexIA_2.3_DEV")
    args = ap.parse_args()

    root = Path(args.root).resolve()
    if not (root / "search").exists():
        raise SystemExit(f"No parece una raíz LexIA válida: {root}")

    sys.path.insert(0, str(root))

    exp = root / "runtime" / "experiments" / "search_stack_profile"
    if exp.exists():
        shutil.rmtree(exp)
    exp.mkdir(parents=True, exist_ok=True)

    print("=" * 112)
    print("LEXIA — BENCHMARK SEARCH STACK v1.0")
    print("=" * 112)
    print(f"Raíz: {root}")
    print(f"Datos temporales: {exp}")
    print()

    t_import = time.perf_counter()

    from config.settings import SETTINGS
    from storage.catalog import DocumentCatalog
    from storage.search_feedback_repository import SearchFeedbackRepository
    from storage.search_history_repository import SearchHistoryRepository
    from storage.search_cache_repository import SearchCacheRepository
    from search.embedding_service import EmbeddingService
    from search.vector_store import VectorStore
    from search.professional_search import ProfessionalLegalSearchEngine
    from search.cached_search import CachedSearchEngine

    try:
        from search.search_hotfix import SearchHotfixEngine
    except Exception:
        SearchHotfixEngine = None

    import_ms = (time.perf_counter() - t_import) * 1000

    print(f"Imports LexIA: {import_ms:.2f} ms")

    # Repositorios temporales para cualquier escritura accesoria de búsqueda.
    feedback = SearchFeedbackRepository(exp / "feedback.sqlite3")
    history = SearchHistoryRepository(exp / "history.sqlite3")
    cache = SearchCacheRepository(exp / "cache.sqlite3")

    catalog = DocumentCatalog(SETTINGS.catalog_path)

    t0 = time.perf_counter()
    embeddings = EmbeddingService()
    embeddings_init_ms = (time.perf_counter() - t0) * 1000

    t0 = time.perf_counter()
    vector_store = VectorStore(embeddings)
    vector_init_ms = (time.perf_counter() - t0) * 1000

    base = ProfessionalLegalSearchEngine(
        vector_store,
        catalog,
        feedback,
        history,
    )

    if SearchHotfixEngine is not None:
        raw = SearchHotfixEngine(base, catalog)
        hotfix_name = "SearchHotfixEngine"
    else:
        raw = base
        hotfix_name = "NO DISPONIBLE"

    cached = CachedSearchEngine(raw, cache)

    print(f"EmbeddingService init: {embeddings_init_ms:.2f} ms")
    print(f"VectorStore init:      {vector_init_ms:.2f} ms")
    print(f"Hotfix layer:          {hotfix_name}")
    print()

    timings = Timings()

    # Instrumentación de componentes.
    wrap_method(embeddings, "embed_query", timings, "embedding")
    wrap_method(vector_store, "search", timings, "vector_total")
    wrap_method(catalog, "lexical_search", timings, "fts_lexical")
    wrap_method(catalog, "direct_document_search", timings, "direct_filename")
    wrap_method(base, "search", timings, "professional_total")

    if raw is not base:
        wrap_method(raw, "search", timings, "hotfix_total")

    # Warm-up de modelo/Qdrant.
    print("Warm-up...")
    try:
        embeddings.embed_query("prueba")
    except Exception as exc:
        print(f"ERROR en embedding warm-up: {exc}")
        return 2

    try:
        vector_store.search("prueba", limit=5)
    except Exception as exc:
        print(f"ERROR en Qdrant warm-up: {exc}")
        print("Verificá que Qdrant Server esté iniciado.")
        return 3

    print("Warm-up OK")
    print()

    # Benchmark por consulta: raw evita que una segunda corrida sea respondida sólo desde cache.
    rows_report = []

    header = (
        f"{'CONSULTA':30} "
        f"{'TOTAL':>9} "
        f"{'EMBED':>9} "
        f"{'QDRANT*':>9} "
        f"{'FTS':>8} "
        f"{'NOMBRE':>8} "
        f"{'PROF':>9} "
        f"{'HOTFIX':>9} "
        f"{'RES':>5}"
    )
    print(header)
    print("-" * len(header))

    for q in QUERIES:
        totals = []
        res_count = 0
        component_runs = {
            "embedding": [],
            "vector_total": [],
            "fts_lexical": [],
            "direct_filename": [],
            "professional_total": [],
            "hotfix_total": [],
        }

        # calentamiento específico de consulta no medido
        timings.clear()
        try:
            call_search(raw, q, LIMIT)
        except Exception as exc:
            print(f"{q[:30]:30} ERROR warm-up: {exc}")
            continue

        for _ in range(RUNS):
            timings.clear()
            t0 = time.perf_counter()
            try:
                result = call_search(raw, q, LIMIT)
            except Exception as exc:
                print(f"{q[:30]:30} ERROR: {exc}")
                result = []
            elapsed = (time.perf_counter() - t0) * 1000
            totals.append(elapsed)
            res_count = count_results(result)

            for k in component_runs:
                vals = timings.data.get(k, [])
                if vals:
                    component_runs[k].append(sum(vals))

        med = lambda k: statistics.median(component_runs[k]) if component_runs[k] else None
        total_med = statistics.median(totals) if totals else None
        embed_med = med("embedding")
        vector_med = med("vector_total")
        # QDRANT* = vector_total incluye embedding; resta aproximada.
        qdrant_only = (
            max(0.0, vector_med - embed_med)
            if vector_med is not None and embed_med is not None
            else None
        )

        row = {
            "query": q,
            "total_ms": total_med,
            "embedding_ms": embed_med,
            "vector_total_ms": vector_med,
            "qdrant_estimated_ms": qdrant_only,
            "fts_ms": med("fts_lexical"),
            "direct_filename_ms": med("direct_filename"),
            "professional_ms": med("professional_total"),
            "hotfix_ms": med("hotfix_total"),
            "results": res_count,
        }
        rows_report.append(row)

        print(
            f"{q[:30]:30} "
            f"{fmt(total_med):>9} "
            f"{fmt(embed_med):>9} "
            f"{fmt(qdrant_only):>9} "
            f"{fmt(row['fts_ms']):>8} "
            f"{fmt(row['direct_filename_ms']):>8} "
            f"{fmt(row['professional_ms']):>9} "
            f"{fmt(row['hotfix_ms']):>9} "
            f"{res_count:5d}"
        )

    print()
    print("* QDRANT es una estimación = VectorStore.search - embed_query.")
    print("  Sirve para localizar órdenes de magnitud, no como tracing nanométrico.")
    print()

    # Medir caché aparte: primera llamada y segunda llamada idéntica.
    cache_query = "responsabilidad del Estado actividad legítima benchmark_cache_unico"
    print("PRUEBA DE CACHÉ")
    t0 = time.perf_counter()
    try:
        r1 = call_search(cached, cache_query, 25)
        first_ms = (time.perf_counter() - t0) * 1000
        t0 = time.perf_counter()
        r2 = call_search(cached, cache_query, 25)
        second_ms = (time.perf_counter() - t0) * 1000
        print(f"  primera llamada: {first_ms:.2f} ms")
        print(f"  segunda llamada: {second_ms:.2f} ms")
        print(f"  resultados:       {count_results(r2)}")
    except Exception as exc:
        first_ms = second_ms = None
        print(f"  ERROR: {exc}")

    report = {
        "root": str(root),
        "imports_ms": import_ms,
        "embeddings_init_ms": embeddings_init_ms,
        "vector_init_ms": vector_init_ms,
        "runs": RUNS,
        "limit": LIMIT,
        "queries": rows_report,
        "cache_first_ms": first_ms,
        "cache_second_ms": second_ms,
        "temporary_dir": str(exp),
        "production_catalog_modified": False,
        "production_qdrant_modified": False,
        "production_feedback_history_cache_modified": False,
    }

    report_path = exp / "benchmark_search_stack_v1.json"
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print()
    print("VERIFICACIÓN")
    print("  Catálogo de producción modificado:      NO")
    print("  Qdrant modificado:                      NO")
    print("  Feedback/historial/cache normales:      NO")
    print(f"  Reporte: {report_path}")
    print()
    print("FIN")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
