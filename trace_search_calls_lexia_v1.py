#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LexIA — Tracer de llamadas de búsqueda v1.0

Instrumenta EN MEMORIA los métodos del catálogo para contar:
- lexical_search
- direct_document_search
y el vector store para:
- search

No modifica código ni bases de producción.
Usa feedback/history temporales.
"""

from __future__ import annotations

import argparse
import inspect
import shutil
import sys
import time
from pathlib import Path

QUERIES = [
    '"solve et repete"',
    '"plazo razonable"',
    '"lucro cesante"',
    'Telecom',
    '"agotamiento internacional"',
]

LIMIT = 20


def shorten(value, n=90):
    s = repr(value)
    return s if len(s) <= n else s[:n-3] + "..."


def call_search(engine, query, limit):
    sig = inspect.signature(engine.search)
    kwargs = {}
    if "limit" in sig.parameters:
        kwargs["limit"] = limit
    if "category" in sig.parameters:
        kwargs["category"] = None
    return engine.search(query, **kwargs)


def instrument(obj, method_name, events, label):
    original = getattr(obj, method_name)

    def wrapper(*args, **kwargs):
        query = None
        limit = None

        if args:
            query = args[0]
            if len(args) > 1:
                limit = args[1]
        if "query" in kwargs:
            query = kwargs["query"]
        if "limit" in kwargs:
            limit = kwargs["limit"]

        t0 = time.perf_counter()
        try:
            result = original(*args, **kwargs)
            count = len(result) if hasattr(result, "__len__") else None
            return result
        finally:
            elapsed = (time.perf_counter() - t0) * 1000
            events.append({
                "layer": label,
                "query": query,
                "limit": limit,
                "ms": elapsed,
                "count": locals().get("count"),
            })

    setattr(obj, method_name, wrapper)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("root", nargs="?", default=r"D:\LexIA_2.3_DEV")
    args = ap.parse_args()

    root = Path(args.root).resolve()
    sys.path.insert(0, str(root))

    exp = root / "runtime" / "experiments" / "search_call_trace"
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

    catalog = DocumentCatalog(SETTINGS.catalog_path)
    feedback = SearchFeedbackRepository(exp / "feedback.sqlite3")
    history = SearchHistoryRepository(exp / "history.sqlite3")
    embeddings = EmbeddingService()
    vector = VectorStore(embeddings)

    base = ProfessionalLegalSearchEngine(
        vector, catalog, feedback, history
    )
    raw = SearchHotfixEngine(base, catalog) if SearchHotfixEngine else base

    events = []
    instrument(catalog, "lexical_search", events, "FTS")
    instrument(catalog, "direct_document_search", events, "NOMBRE")
    instrument(vector, "search", events, "VECTOR")

    # Warm-up del modelo y Qdrant, fuera del tracing útil
    try:
        embeddings.embed_query("prueba")
        vector.search("prueba", 3)
    except Exception as exc:
        raise SystemExit(f"Warm-up falló: {exc}")

    print("=" * 110)
    print("LEXIA — TRACE DE LLAMADAS SEARCH v1.0")
    print("=" * 110)
    print()

    for q in QUERIES:
        events.clear()
        t0 = time.perf_counter()
        try:
            results = call_search(raw, q, LIMIT)
            total = (time.perf_counter() - t0) * 1000
        except Exception as exc:
            print(f"Consulta: {q}")
            print(f"ERROR: {exc}\n")
            continue

        print(f"CONSULTA: {q}")
        print(f"TOTAL: {total:.2f} ms | resultados: {len(results)}")
        print()

        by_layer = {}
        for e in events:
            by_layer.setdefault(e["layer"], []).append(e)

        for layer in ("FTS", "NOMBRE", "VECTOR"):
            vals = by_layer.get(layer, [])
            total_layer = sum(x["ms"] for x in vals)
            print(f"{layer}: {len(vals)} llamadas | {total_layer:.2f} ms acumulados")
            for i, e in enumerate(vals, 1):
                print(
                    f"  {i:02d}. {e['ms']:8.2f} ms"
                    f" | limit={e['limit']}"
                    f" | resultados={e['count']}"
                    f" | q={shorten(e['query'])}"
                )
            print()

        accounted = sum(e["ms"] for e in events)
        print(f"Tiempo instrumentado acumulado: {accounted:.2f} ms")
        print(f"Resto aproximado del pipeline:  {max(0,total-accounted):.2f} ms")
        print("-" * 110)
        print()

    print("No se modificó ninguna base de producción.")


if __name__ == "__main__":
    main()
