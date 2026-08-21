#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LexIA — Benchmark FTS en dos etapas v1.0

SOLO LECTURA sobre:
- runtime/lexia_catalog.sqlite3
- runtime/experiments/lexia_document_fts_test.sqlite3

Compara:
A) FTS actual por fragmentos, top 100 filas
B) FTS por fragmentos ampliado y colapsado por documento
C) FTS documental sin snippet, top 100 docs
D) FTS documental top 20 + snippet sólo para esos 20

No modifica producción ni el experimento existente.
"""

from __future__ import annotations

import argparse
import sqlite3
import statistics
import time
from pathlib import Path

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

RUNS = 5
FRAG_FETCH = 1000
DOC_LIMIT = 100
SNIPPET_LIMIT = 20


def open_ro(path: Path) -> sqlite3.Connection:
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


def median_run(fn):
    vals = []
    result = None
    for _ in range(RUNS):
        t0 = time.perf_counter()
        result = fn()
        vals.append((time.perf_counter() - t0) * 1000)
    return statistics.median(vals), result


def frag_top100(con, q):
    sql = """
        SELECT
            document_path,
            fragment_index,
            document_name,
            bm25(fragments_fts) AS score
        FROM fragments_fts
        WHERE fragments_fts MATCH ?
        ORDER BY score
        LIMIT 100
    """
    return con.execute(sql, (q,)).fetchall()


def frag_collapsed(con, q):
    # Recupera más fragmentos muy baratos, y colapsa en Python por documento
    # conservando el mejor score de cada documento.
    sql = """
        SELECT
            document_path,
            fragment_index,
            document_name,
            category,
            text_content,
            bm25(fragments_fts) AS score
        FROM fragments_fts
        WHERE fragments_fts MATCH ?
        ORDER BY score
        LIMIT ?
    """
    rows = con.execute(sql, (q, FRAG_FETCH)).fetchall()
    seen = {}
    for r in rows:
        p = r["document_path"]
        if p not in seen:
            seen[p] = r
            if len(seen) >= DOC_LIMIT:
                break
    return list(seen.values())


def doc_ids(con, q):
    sql = """
        SELECT
            rowid,
            document_path,
            document_name,
            category,
            bm25(document_fts) AS score
        FROM document_fts
        WHERE document_fts MATCH ?
        ORDER BY score
        LIMIT ?
    """
    return con.execute(sql, (q, DOC_LIMIT)).fetchall()


def doc_top20_with_snippet(con, q):
    # Genera snippet sólo para los 20 mejores documentos.
    sql = """
        SELECT
            document_path,
            document_name,
            category,
            bm25(document_fts) AS score,
            snippet(document_fts, 3, '[[', ']]', ' … ', 28) AS snippet
        FROM document_fts
        WHERE document_fts MATCH ?
        ORDER BY score
        LIMIT ?
    """
    return con.execute(sql, (q, SNIPPET_LIMIT)).fetchall()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("root", nargs="?", default=r"D:\LexIA_2.3_DEV")
    args = ap.parse_args()

    root = Path(args.root).resolve()
    catalog = root / "runtime" / "lexia_catalog.sqlite3"
    exp = root / "runtime" / "experiments" / "lexia_document_fts_test.sqlite3"

    if not catalog.exists():
        raise SystemExit(f"No existe: {catalog}")
    if not exp.exists():
        raise SystemExit(
            "No existe la base experimental documental.\n"
            f"Esperada: {exp}\n"
            "Ejecutá primero experimentar_fts_documental_lexia_v1.py"
        )

    frag = open_ro(catalog)
    doc = open_ro(exp)

    print("=" * 118)
    print("LEXIA — BENCHMARK FTS EN DOS ETAPAS v1.0 (SOLO LECTURA)")
    print("=" * 118)
    print(f"Fragmentos candidatos para colapso: {FRAG_FETCH}")
    print(f"Documentos objetivo:                {DOC_LIMIT}")
    print(f"Snippets documentales:              {SNIPPET_LIMIT}")
    print()

    hdr = (
        f"{'CONSULTA':32} "
        f"{'frag100':>9} "
        f"{'docs':>5} "
        f"{'frag→doc':>10} "
        f"{'docs':>5} "
        f"{'doc IDs':>9} "
        f"{'doc+snip20':>12}"
    )
    print(hdr)
    print("-" * len(hdr))

    for q in QUERIES:
        # warmups
        frag_top100(frag, q)
        frag_collapsed(frag, q)
        doc_ids(doc, q)
        doc_top20_with_snippet(doc, q)

        t_a, a = median_run(lambda: frag_top100(frag, q))
        t_b, b = median_run(lambda: frag_collapsed(frag, q))
        t_c, c = median_run(lambda: doc_ids(doc, q))
        t_d, d = median_run(lambda: doc_top20_with_snippet(doc, q))

        a_docs = len({r["document_path"] for r in a})
        b_docs = len(b)

        print(
            f"{q[:32]:32} "
            f"{t_a:9.2f} "
            f"{a_docs:5d} "
            f"{t_b:10.2f} "
            f"{b_docs:5d} "
            f"{t_c:9.2f} "
            f"{t_d:12.2f}"
        )

    print()
    print("Lectura de columnas:")
    print("  frag100     = FTS actual: top 100 fragmentos")
    print("  docs        = documentos únicos dentro de esos 100 fragmentos")
    print("  frag→doc    = hasta 1000 fragmentos, colapsados hasta 100 documentos únicos")
    print("  doc IDs     = FTS documental sin generar snippets")
    print("  doc+snip20  = FTS documental, pero snippet sólo para los primeros 20")
    print()
    print("No se modificó ninguna base.")

    frag.close()
    doc.close()


if __name__ == "__main__":
    main()
