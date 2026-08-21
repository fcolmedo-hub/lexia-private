#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

DEFAULT_QUERY = "plazo razonable del proceso penal"

class Recorder:
    def __init__(self):
        self.events = []
    def add(self, layer, query, limit, elapsed_ms, count=None):
        self.events.append({"layer": layer, "query": query, "limit": limit, "ms": elapsed_ms, "count": count})
    def by(self, layer):
        return [e for e in self.events if e["layer"] == layer]

def result_count(result):
    try:
        return len(result)
    except Exception:
        return None

def instrument_search(obj, recorder, layer):
    if obj is None or not hasattr(obj, "search"):
        return False
    original = obj.search
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
            recorder.add(layer, query, limit, (time.perf_counter() - t0) * 1000, result_count(result))
    obj.search = wrapped
    return True

def instrument_method(obj, name, recorder, layer):
    if obj is None or not hasattr(obj, name):
        return False
    original = getattr(obj, name)
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
            recorder.add(layer, query, limit, (time.perf_counter() - t0) * 1000, result_count(result))
    setattr(obj, name, wrapped)
    return True

def unwrap_chain(obj, max_depth=10):
    seen, out = set(), []
    current = obj
    for _ in range(max_depth):
        if current is None or id(current) in seen:
            break
        seen.add(id(current))
        out.append(current)
        nxt = None
        for attr in ("delegate", "engine", "search_engine", "base", "wrapped"):
            value = getattr(current, attr, None)
            if value is not None and value is not current:
                nxt = value
                break
        current = nxt
    return out

def short(value, n=105):
    text = str(value)
    return text if len(text) <= n else text[: n - 3] + "..."

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("root", nargs="?", default=r"D:\LexIA_2.3_DEV")
    parser.add_argument("--query", default=DEFAULT_QUERY)
    parser.add_argument("--max-sources", type=int, default=None)
    args = parser.parse_args()

    root = Path(args.root).resolve()
    query = str(args.query).strip()
    if not query:
        raise SystemExit("Consulta vacía.")

    sys.path.insert(0, str(root))
    from services.application import LexIAApplication

    print("=" * 116)
    print("LEXIA — PRUEBA 8: TRACE REAL CONTEXT BUILDER")
    print("=" * 116)
    print("Consulta:", query)
    print()

    app = LexIAApplication()
    builder = app.context_builder
    interpreted = app.interpreted_search
    cached = app.search
    raw = app.raw_search
    vector = app.vector_store

    print("STACK REAL")
    print("  Context Builder:     ", type(builder).__name__)
    print("  Interpreted Search:  ", type(interpreted).__name__)
    print("  Search:              ", type(cached).__name__)
    print("  Raw Search:          ", type(raw).__name__)
    for i, obj in enumerate(unwrap_chain(raw), 1):
        print(f"  Raw layer {i}:         {type(obj).__name__}")
    fs_enabled = (root / "runtime" / "fast_search_1_0" / "enabled").exists()
    print("  Fast Search enabled: ", "SI" if fs_enabled else "NO")
    print()

    recorder = Recorder()
    instrument_search(cached, recorder, "SEARCH_REAL")
    instrument_search(raw, recorder, "RAW_REAL")
    instrument_search(vector, recorder, "VECTOR_REAL")

    proxy = getattr(raw, "catalog_proxy", None)
    if proxy is not None:
        instrument_method(proxy, "lexical_search", recorder, "FTS_FAST_PROXY")
        instrument_method(proxy, "direct_document_search", recorder, "NOMBRE_FAST_PROXY")
        underlying_catalog = getattr(proxy, "_catalog", None)
        if underlying_catalog is not None:
            instrument_method(underlying_catalog, "lexical_search", recorder, "FTS_CATALOGO")
            instrument_method(underlying_catalog, "direct_document_search", recorder, "NOMBRE_CATALOGO")
    else:
        instrument_method(app.catalog, "lexical_search", recorder, "FTS_CATALOGO")
        instrument_method(app.catalog, "direct_document_search", recorder, "NOMBRE_CATALOGO")

    print("Warm-up vectorial...")
    try:
        app.embeddings.embed_query("warmup prueba 8")
        app.vector_store.search("warmup prueba 8", limit=3)
    except Exception as exc:
        print("AVISO warm-up:", exc)
    recorder.events.clear()
    print("Warm-up OK")
    print()

    t0 = time.perf_counter()
    try:
        kwargs = {}
        if args.max_sources is not None:
            kwargs["max_sources"] = args.max_sources
        package = builder.build_research_package(query=query, **kwargs)
        error = None
    except Exception as exc:
        package = None
        error = exc
    total_ms = (time.perf_counter() - t0) * 1000

    print("=" * 116)
    print("RESULTADO REAL")
    print("=" * 116)
    print(f"Tiempo total observado: {total_ms/1000:.3f} s")
    if error:
        print("ERROR:", repr(error))

    print()
    print("CONSULTAS QUE REALMENTE LLEGARON A app.search")
    search_events = recorder.by("SEARCH_REAL")
    if not search_events:
        print("  [ninguna llamada registrada]")
    else:
        for i, e in enumerate(search_events, 1):
            print(f"  Q{i}. {e['ms']/1000:8.3f} s | limit={e['limit']} | resultados={e['count']} | {short(e['query'])}")

    print()
    print("RAW SEARCH REAL")
    raw_events = recorder.by("RAW_REAL")
    if not raw_events:
        print("  [ninguna: posible cache hit]")
    else:
        for i, e in enumerate(raw_events, 1):
            print(f"  R{i}. {e['ms']/1000:8.3f} s | limit={e['limit']} | resultados={e['count']} | {short(e['query'])}")

    print()
    for layer in ("FTS_FAST_PROXY","FTS_CATALOGO","NOMBRE_FAST_PROXY","NOMBRE_CATALOGO","VECTOR_REAL"):
        events = recorder.by(layer)
        if not events:
            continue
        print(layer)
        print(f"  llamadas: {len(events)}")
        print(f"  acumulado: {sum(e['ms'] for e in events):.2f} ms")
        for i, e in enumerate(events, 1):
            print(f"    {i:02d}. {e['ms']:9.2f} ms | limit={e['limit']} | res={e['count']} | {short(e['query'])}")
        print()

    print("RANKING DE CONSULTAS REALES")
    ordered = sorted(search_events, key=lambda e: e["ms"], reverse=True)
    for i, e in enumerate(ordered, 1):
        pct = e["ms"] / total_ms * 100 if total_ms else 0
        print(f"  {i}. {e['ms']/1000:.3f} s ({pct:.1f}%) — {short(e['query'])}")

    print()
    print("VERIFICACIÓN")
    print("  Código modificado por esta prueba: NO")
    print("  Se ejecutó el flujo real de búsqueda de LexIA: SI")
    print("FIN")

if __name__ == "__main__":
    main()
