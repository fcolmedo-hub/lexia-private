#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LexIA — Diagnóstico FTS actual v1.0
SOLO LECTURA sobre las bases de LexIA.
No modifica catálogo, FTS, Qdrant, Knowledge ni documentos.
"""

from __future__ import annotations

import argparse
import json
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
LIMIT = 100


def human_bytes(n: int | float) -> str:
    x = float(n)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if x < 1024 or unit == "TB":
            return f"{x:,.2f} {unit}"
        x /= 1024
    return f"{x:,.2f} TB"


def scalar(con: sqlite3.Connection, sql: str, params=()):
    row = con.execute(sql, params).fetchone()
    return row[0] if row else None


def table_exists(con: sqlite3.Connection, name: str) -> bool:
    return bool(
        scalar(
            con,
            "SELECT COUNT(*) FROM sqlite_master WHERE name=?",
            (name,),
        )
    )


def find_catalog(root: Path) -> Path:
    candidates = [
        root / "runtime" / "lexia_catalog.sqlite3",
        root / "storage" / "lexia_catalog.sqlite3",
        root / "lexia_catalog.sqlite3",
    ]
    for p in candidates:
        if p.exists():
            return p

    matches = list(root.rglob("lexia_catalog.sqlite3"))
    matches = [p for p in matches if "backup" not in str(p).lower() and "bckup" not in str(p).lower()]
    if len(matches) == 1:
        return matches[0]
    if not matches:
        raise FileNotFoundError(
            f"No encontré lexia_catalog.sqlite3 debajo de {root}"
        )
    raise RuntimeError(
        "Encontré más de un catálogo activo posible:\n  "
        + "\n  ".join(map(str, matches))
    )


def bench(con: sqlite3.Connection, query: str) -> dict:
    sql = """
        SELECT
            fts.document_path,
            CAST(fts.fragment_index AS INTEGER) AS fragment_index,
            fts.category,
            fts.document_name,
            bm25(fragments_fts) AS lexical_score,
            snippet(fragments_fts, -1, '[[', ']]', ' … ', 28) AS snippet
        FROM fragments_fts AS fts
        WHERE fragments_fts MATCH ?
        ORDER BY lexical_score
        LIMIT ?
    """

    # calentamiento
    con.execute(sql, (query, LIMIT)).fetchall()

    times = []
    rows = []
    for _ in range(RUNS):
        t0 = time.perf_counter()
        rows = con.execute(sql, (query, LIMIT)).fetchall()
        times.append((time.perf_counter() - t0) * 1000)

    unique_docs = len({r["document_path"] for r in rows})
    return {
        "query": query,
        "rows": len(rows),
        "unique_documents_in_top": unique_docs,
        "min_ms": min(times),
        "median_ms": statistics.median(times),
        "mean_ms": statistics.mean(times),
        "max_ms": max(times),
        "runs_ms": times,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "root",
        nargs="?",
        default=r"D:\LexIA_2.3_DEV",
        help=r"Raíz de LexIA. Default: D:\LexIA_2.3_DEV",
    )
    args = ap.parse_args()

    root = Path(args.root).resolve()
    catalog = find_catalog(root)

    uri = catalog.resolve().as_uri() + "?mode=ro"
    con = sqlite3.connect(uri, uri=True)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA query_only=ON")
    con.execute("PRAGMA temp_store=MEMORY")
    con.execute("PRAGMA cache_size=-64000")
    try:
        con.execute("PRAGMA mmap_size=268435456")
    except Exception:
        pass

    print("=" * 92)
    print("LEXIA — DIAGNÓSTICO FTS ACTUAL v1.0 (SOLO LECTURA)")
    print("=" * 92)
    print(f"Raíz:    {root}")
    print(f"Catálogo:{catalog}")
    print(f"Tamaño:  {human_bytes(catalog.stat().st_size)}")
    print()

    tables = [
        "documents",
        "document_locations",
        "fragments",
        "fragments_fts",
    ]
    print("TABLAS")
    for t in tables:
        print(f"  {t:22} {'OK' if table_exists(con, t) else 'NO EXISTE'}")
    print()

    if not table_exists(con, "documents"):
        raise SystemExit("No existe tabla documents.")

    docs_total = scalar(con, "SELECT COUNT(*) FROM documents") or 0
    docs_active = scalar(con, "SELECT COUNT(*) FROM documents WHERE COALESCE(is_deleted,0)=0") or 0

    cols = {r["name"] for r in con.execute("PRAGMA table_info(documents)").fetchall()}
    has_text = "text_content" in cols
    has_hash = "content_hash" in cols
    has_dup = "duplicate_of" in cols

    print("DOCUMENTOS")
    print(f"  total:                    {docs_total:,}")
    print(f"  activos:                  {docs_active:,}")

    if has_text:
        docs_text = scalar(
            con,
            """
            SELECT COUNT(*)
            FROM documents
            WHERE COALESCE(is_deleted,0)=0
              AND text_content IS NOT NULL
              AND length(trim(text_content)) > 0
            """,
        ) or 0
        chars = scalar(
            con,
            """
            SELECT COALESCE(SUM(length(text_content)),0)
            FROM documents
            WHERE COALESCE(is_deleted,0)=0
            """,
        ) or 0
        print(f"  activos con texto:        {docs_text:,} ({(docs_text/docs_active*100 if docs_active else 0):.2f}%)")
        print(f"  caracteres texto docs:    {chars:,}")
        print(f"  promedio chars/documento: {(chars/docs_text if docs_text else 0):,.0f}")
    else:
        docs_text = 0
        print("  text_content:             COLUMNA NO EXISTE")

    if has_hash:
        hashes = scalar(
            con,
            """
            SELECT COUNT(DISTINCT content_hash)
            FROM documents
            WHERE COALESCE(is_deleted,0)=0
              AND content_hash IS NOT NULL
              AND content_hash <> ''
            """,
        ) or 0
        print(f"  hashes únicos activos:    {hashes:,}")

    if has_dup:
        dups = scalar(
            con,
            """
            SELECT COUNT(*)
            FROM documents
            WHERE COALESCE(is_deleted,0)=0
              AND duplicate_of IS NOT NULL
              AND duplicate_of <> ''
            """,
        ) or 0
        print(f"  duplicados activos:       {dups:,}")

    print()

    if table_exists(con, "fragments"):
        fragments = scalar(con, "SELECT COUNT(*) FROM fragments") or 0
        frag_docs = scalar(con, "SELECT COUNT(DISTINCT document_path) FROM fragments") or 0
        frag_chars = scalar(con, "SELECT COALESCE(SUM(length(text_content)),0) FROM fragments") or 0
        print("FRAGMENTOS")
        print(f"  filas:                    {fragments:,}")
        print(f"  documentos representados: {frag_docs:,}")
        print(f"  caracteres acumulados:    {frag_chars:,}")
        print(f"  fragmentos/documento:     {(fragments/frag_docs if frag_docs else 0):.2f}")
        print()

    if table_exists(con, "fragments_fts"):
        fts_rows = scalar(con, "SELECT COUNT(*) FROM fragments_fts") or 0
        fts_docs = scalar(con, "SELECT COUNT(DISTINCT document_path) FROM fragments_fts") or 0
        schema = scalar(
            con,
            "SELECT sql FROM sqlite_master WHERE name='fragments_fts'",
        )
        print("FTS5 ACTUAL")
        print(f"  filas FTS:                {fts_rows:,}")
        print(f"  documentos en FTS:        {fts_docs:,}")
        print("  esquema:")
        print("   ", (schema or "").replace("\n", " "))
        print()

        print("BENCHMARK FTS5 ACTUAL — fragmentos + BM25 + snippet")
        print(f"  Corridas por consulta: {RUNS}")
        print(f"  LIMIT: {LIMIT}")
        print()

        results = []
        for q in QUERIES:
            try:
                r = bench(con, q)
                results.append(r)
                print(f"Consulta: {q}")
                print(f"  filas top:          {r['rows']}")
                print(f"  docs únicos top:    {r['unique_documents_in_top']}")
                print(f"  mínimo:             {r['min_ms']:.2f} ms")
                print(f"  mediana:            {r['median_ms']:.2f} ms")
                print(f"  promedio:           {r['mean_ms']:.2f} ms")
                print(f"  máximo:             {r['max_ms']:.2f} ms")
                print("  corridas:           " + ", ".join(f"{x:.2f}" for x in r["runs_ms"]) + " ms")
                print()
            except Exception as exc:
                print(f"Consulta: {q}")
                print(f"  ERROR: {exc}")
                print()

    # Diagnóstico de relación texto completo vs fragmentos.
    print("-" * 92)
    print("LECTURA PRELIMINAR")
    if has_text and docs_text:
        print("✓ LexIA ya conserva texto completo en documents.text_content.")
        print("  Esto permitiría construir un FTS documental sin volver a abrir los PDFs.")
    else:
        print("! No confirmé texto completo utilizable en documents.text_content.")
    if table_exists(con, "fragments_fts"):
        print("✓ LexIA ya tiene FTS5, actualmente a nivel de fragmentos.")
        print("  La siguiente prueba será comparar este FTS con un FTS documental temporal.")
    print("✓ No se modificó ninguna base.")
    con.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
