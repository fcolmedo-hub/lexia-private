#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LexIA — Benchmark política de búsqueda rápida v1.0

NO modifica producción.

Compara, sobre las consultas de prueba:
A) búsquedas lexicales que hoy aparecen en el trace
B) política rápida:
   - frase exacta primero
   - OR sólo como fallback si la frase exacta devuelve pocos documentos
   - FTS separado para nombres de documentos (temporal)
   - medición vectorial única sobre la consulta original

Crea únicamente:
runtime/experiments/fast_search_policy/document_names_fts.sqlite3
"""

from __future__ import annotations

import argparse
import sqlite3
import statistics
import sys
import time
from pathlib import Path

TESTS = {
    '"solve et repete"': [
        '"solve" OR "repete"',
        '"pago" OR "previo"',
        '"requisito" OR "pago" OR "previo"',
        '"solve et repete"',
    ],
    '"plazo razonable"': [
        '"plazo" OR "razonable"',
        '"duración" OR "razonable" OR "del" OR "proceso"',
        '"dilaciones" OR "indebidas"',
        '"plazo razonable"',
    ],
    '"lucro cesante"': [
        '"lucro" OR "cesante"',
        '"lucro cesante"',
    ],
    'Telecom': [
        '"Telecom"',
        'Telecom',
    ],
    '"agotamiento internacional"': [
        '"agotamiento" OR "internacional"',
        '"agotamiento internacional"',
    ],
}

RUNS = 5
LEX_LIMIT = 60
VECTOR_LIMIT = 24
FALLBACK_MIN_DOCS = 10


def ro(path: Path):
    con = sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA query_only=ON")
    con.execute("PRAGMA temp_store=MEMORY")
    con.execute("PRAGMA cache_size=-64000")
    try:
        con.execute("PRAGMA mmap_size=268435456")
    except Exception:
        pass
    return con


def timed(fn, runs=RUNS):
    vals, result = [], None
    fn()  # warmup
    for _ in range(runs):
        t0 = time.perf_counter()
        result = fn()
        vals.append((time.perf_counter() - t0) * 1000)
    return statistics.median(vals), result


def lexical(con, query, limit=LEX_LIMIT):
    rows = con.execute(
        """
        SELECT document_path,
               fragment_index,
               bm25(fragments_fts) score
        FROM fragments_fts
        WHERE fragments_fts MATCH ?
        ORDER BY score
        LIMIT ?
        """,
        (query, limit),
    ).fetchall()
    return rows


def unique_docs(rows):
    return len({r["document_path"] for r in rows})


def build_name_fts(catalog: Path, name_db: Path):
    if name_db.exists():
        name_db.unlink()
    src = ro(catalog)
    dst = sqlite3.connect(name_db)
    dst.execute("PRAGMA journal_mode=OFF")
    dst.execute("PRAGMA synchronous=OFF")
    dst.execute("""
        CREATE VIRTUAL TABLE names_fts USING fts5(
            document_path UNINDEXED,
            document_name,
            tokenize='unicode61 remove_diacritics 2'
        )
    """)
    rows = src.execute(
        """
        SELECT path, name
        FROM documents
        WHERE COALESCE(is_deleted,0)=0
          AND name IS NOT NULL
          AND trim(name) <> ''
        """
    )
    dst.executemany(
        "INSERT INTO names_fts(document_path, document_name) VALUES (?,?)",
        ((r["path"], r["name"]) for r in rows),
    )
    dst.commit()
    src.close()
    dst.close()


def name_fts_search(con, raw_query, limit=20):
    # Normaliza para FTS de nombres: palabras AND implícito.
    q = str(raw_query).strip().strip('"').strip()
    if not q:
        return []
    # Para evitar sintaxis especial accidental, entrecomillamos cada token.
    terms = [x for x in q.replace("\\", " ").replace("/", " ").split() if x]
    safe = " ".join('"' + x.replace('"', '""') + '"' for x in terms)
    if not safe:
        return []
    return con.execute(
        """
        SELECT document_path, document_name, bm25(names_fts) score
        FROM names_fts
        WHERE names_fts MATCH ?
        ORDER BY score
        LIMIT ?
        """,
        (safe, limit),
    ).fetchall()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("root", nargs="?", default=r"D:\LexIA_2.3_DEV")
    args = ap.parse_args()

    root = Path(args.root).resolve()
    catalog = root / "runtime" / "lexia_catalog.sqlite3"
    if not catalog.exists():
        raise SystemExit(f"No existe {catalog}")

    exp = root / "runtime" / "experiments" / "fast_search_policy"
    exp.mkdir(parents=True, exist_ok=True)
    names_db = exp / "document_names_fts.sqlite3"

    print("=" * 112)
    print("LEXIA — BENCHMARK POLÍTICA DE BÚSQUEDA RÁPIDA v1.0")
    print("=" * 112)
    print()
    print("1/3 Creando FTS temporal de nombres...")
    t0 = time.perf_counter()
    build_name_fts(catalog, names_db)
    print(f"  completado en {(time.perf_counter()-t0):.2f} s")
    print(f"  tamaño: {names_db.stat().st_size / 1024 / 1024:.2f} MB")
    print()

    cat = ro(catalog)
    ndb = ro(names_db)

    # Qdrant + embedding real, sólo lectura
    sys.path.insert(0, str(root))
    from search.embedding_service import EmbeddingService
    from search.vector_store import VectorStore

    emb = EmbeddingService()
    vec = VectorStore(emb)

    # warmup
    emb.embed_query("prueba")
    vec.search("prueba", limit=3)

    print("2/3 Comparando política actual observada vs política rápida")
    print()
    header = (
        f"{'CONSULTA':30} "
        f"{'FTS ACTUAL':>11} "
        f"{'FTS RÁPIDO':>11} "
        f"{'DOCS':>6} "
        f"{'NOMBRE FTS':>11} "
        f"{'VECTOR 1X':>10} "
        f"{'EST.RÁPIDA':>11}"
    )
    print(header)
    print("-" * len(header))

    for original, current_queries in TESTS.items():

        # Política observada: suma de las búsquedas FTS trazadas.
        current_times = []
        for cq in current_queries:
            t, _ = timed(lambda cq=cq: lexical(cat, cq))
            current_times.append(t)
        current_total = sum(current_times)

        # Política rápida:
        # exacta primero
        exact = original
        t_exact, exact_rows = timed(lambda: lexical(cat, exact))
        exact_docs = unique_docs(exact_rows)

        fast_fts = t_exact
        final_rows = exact_rows

        # Fallback sólo si no alcanza cobertura mínima.
        if exact_docs < FALLBACK_MIN_DOCS:
            stripped = original.strip().strip('"')
            terms = [x for x in stripped.split() if x]
            if len(terms) > 1:
                fallback = " OR ".join(f'"{x}"' for x in terms)
                t_fb, fb_rows = timed(lambda: lexical(cat, fallback))
                fast_fts += t_fb
                final_rows = fb_rows if unique_docs(fb_rows) > exact_docs else exact_rows

        docs = unique_docs(final_rows)

        # nombre via FTS temporal
        t_name, name_rows = timed(lambda: name_fts_search(ndb, original, 20))

        # una única búsqueda vectorial
        t_vec, vector_rows = timed(lambda: vec.search(original, limit=VECTOR_LIMIT), runs=3)

        estimated = fast_fts + t_name + t_vec

        print(
            f"{original[:30]:30} "
            f"{current_total:11.2f} "
            f"{fast_fts:11.2f} "
            f"{docs:6d} "
            f"{t_name:11.2f} "
            f"{t_vec:10.2f} "
            f"{estimated:11.2f}"
        )

    print()
    print("3/3 Lectura")
    print("FTS ACTUAL = suma de las consultas FTS observadas en el trace anterior.")
    print("FTS RÁPIDO = frase original exacta; OR sólo si devuelve menos de "
          f"{FALLBACK_MIN_DOCS} documentos.")
    print("NOMBRE FTS = búsqueda en índice temporal específico de nombres, no LIKE '%...%'.")
    print("VECTOR 1X  = una sola búsqueda semántica sobre la consulta original.")
    print("EST.RÁPIDA = suma aproximada FTS rápido + nombre FTS + vector.")
    print()
    print("No se modificó ninguna base de producción.")
    print(f"Índice temporal: {names_db}")

    cat.close()
    ndb.close()


if __name__ == "__main__":
    main()
