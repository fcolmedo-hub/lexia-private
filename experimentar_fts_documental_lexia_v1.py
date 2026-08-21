#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LexIA — Experimento FTS documental v1.0
Crea una base TEMPORAL/EXPERIMENTAL separada de producción y compara:
- FTS actual por fragmentos
- FTS experimental por documento completo

NO modifica:
- runtime/lexia_catalog.sqlite3
- Qdrant
- Knowledge
- PDFs
"""

from __future__ import annotations

import argparse
import json
import shutil
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


def find_catalog(root: Path) -> Path:
    p = root / "runtime" / "lexia_catalog.sqlite3"
    if p.exists():
        return p
    matches = [
        x for x in root.rglob("lexia_catalog.sqlite3")
        if "backup" not in str(x).lower() and "bckup" not in str(x).lower()
    ]
    if len(matches) == 1:
        return matches[0]
    if not matches:
        raise FileNotFoundError("No encontré lexia_catalog.sqlite3")
    raise RuntimeError("Hay más de un catálogo posible:\n" + "\n".join(map(str, matches)))


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


def bench_fragment_fts(con: sqlite3.Connection, query: str) -> dict:
    sql = """
        SELECT
            fts.document_path,
            CAST(fts.fragment_index AS INTEGER) AS fragment_index,
            fts.category,
            fts.document_name,
            bm25(fragments_fts) AS score,
            snippet(fragments_fts, -1, '[[', ']]', ' … ', 28) AS snippet
        FROM fragments_fts AS fts
        WHERE fragments_fts MATCH ?
        ORDER BY score
        LIMIT ?
    """
    con.execute(sql, (query, LIMIT)).fetchall()
    times = []
    rows = []
    for _ in range(RUNS):
        t0 = time.perf_counter()
        rows = con.execute(sql, (query, LIMIT)).fetchall()
        times.append((time.perf_counter() - t0) * 1000)
    return {
        "rows": len(rows),
        "unique_docs": len({r["document_path"] for r in rows}),
        "median_ms": statistics.median(times),
        "mean_ms": statistics.mean(times),
        "min_ms": min(times),
        "max_ms": max(times),
    }


def bench_document_fts(con: sqlite3.Connection, query: str) -> dict:
    sql = """
        SELECT
            fts.document_path,
            fts.document_name,
            fts.category,
            bm25(document_fts) AS score,
            snippet(document_fts, 3, '[[', ']]', ' … ', 28) AS snippet
        FROM document_fts AS fts
        WHERE document_fts MATCH ?
        ORDER BY score
        LIMIT ?
    """
    con.execute(sql, (query, LIMIT)).fetchall()
    times = []
    rows = []
    for _ in range(RUNS):
        t0 = time.perf_counter()
        rows = con.execute(sql, (query, LIMIT)).fetchall()
        times.append((time.perf_counter() - t0) * 1000)
    return {
        "rows": len(rows),
        "unique_docs": len(rows),
        "median_ms": statistics.median(times),
        "mean_ms": statistics.mean(times),
        "min_ms": min(times),
        "max_ms": max(times),
    }


def create_experiment(catalog: Path, out_db: Path) -> dict:
    out_db.parent.mkdir(parents=True, exist_ok=True)
    if out_db.exists():
        out_db.unlink()

    src = open_ro(catalog)
    dst = sqlite3.connect(out_db)
    dst.execute("PRAGMA journal_mode=OFF")
    dst.execute("PRAGMA synchronous=OFF")
    dst.execute("PRAGMA temp_store=MEMORY")
    dst.execute("PRAGMA cache_size=-64000")

    dst.execute("""
        CREATE VIRTUAL TABLE document_fts USING fts5(
            document_path UNINDEXED,
            document_name UNINDEXED,
            category UNINDEXED,
            text_content,
            tokenize='unicode61 remove_diacritics 2'
        )
    """)

    sql = """
        SELECT path, name, category, text_content
        FROM documents
        WHERE COALESCE(is_deleted,0)=0
          AND text_content IS NOT NULL
          AND length(trim(text_content)) > 0
          AND (duplicate_of IS NULL OR duplicate_of = '')
        ORDER BY path
    """

    inserted = 0
    chars = 0
    started = time.perf_counter()
    batch = []

    for row in src.execute(sql):
        text = row["text_content"] or ""
        batch.append((
            row["path"],
            row["name"],
            row["category"],
            text,
        ))
        chars += len(text)

        if len(batch) >= 1000:
            dst.executemany("""
                INSERT INTO document_fts(
                    document_path, document_name, category, text_content
                ) VALUES (?, ?, ?, ?)
            """, batch)
            inserted += len(batch)
            batch.clear()
            if inserted % 10000 == 0:
                print(f"  cargados: {inserted:,} documentos")

    if batch:
        dst.executemany("""
            INSERT INTO document_fts(
                document_path, document_name, category, text_content
            ) VALUES (?, ?, ?, ?)
        """, batch)
        inserted += len(batch)

    dst.commit()
    elapsed = time.perf_counter() - started

    src.close()
    dst.close()

    return {
        "inserted": inserted,
        "chars": chars,
        "elapsed_seconds": elapsed,
        "size_bytes": out_db.stat().st_size,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "root",
        nargs="?",
        default=r"D:\LexIA_2.3_DEV",
    )
    ap.add_argument(
        "--keep",
        action="store_true",
        help="Conservar la base experimental al terminar.",
    )
    args = ap.parse_args()

    root = Path(args.root).resolve()
    catalog = find_catalog(root)
    exp_dir = root / "runtime" / "experiments"
    exp_db = exp_dir / "lexia_document_fts_test.sqlite3"
    report_path = exp_dir / "lexia_document_fts_test_report.json"

    print("=" * 96)
    print("LEXIA — EXPERIMENTO FTS DOCUMENTAL v1.0")
    print("=" * 96)
    print(f"Catálogo producción: {catalog}")
    print(f"Base experimental:   {exp_db}")
    print()
    print("IMPORTANTE: la base de producción se abre en modo SOLO LECTURA.")
    print()

    print("1/3 Construyendo FTS documental experimental...")
    stats = create_experiment(catalog, exp_db)

    print()
    print("Construcción completada")
    print(f"  documentos cargados: {stats['inserted']:,}")
    print(f"  caracteres:           {stats['chars']:,}")
    print(f"  tiempo:                {stats['elapsed_seconds']:.2f} s")
    print(f"  tamaño experimental:   {human_bytes(stats['size_bytes'])}")
    print()

    prod = open_ro(catalog)
    exp = open_ro(exp_db)

    print("2/3 Comparando búsquedas")
    print()
    print(f"{'CONSULTA':34} {'FRAG ms':>10} {'DOC ms':>10} {'FRAG docs':>11} {'DOC docs':>10}")
    print("-" * 82)

    comparisons = []

    for q in QUERIES:
        try:
            frag = bench_fragment_fts(prod, q)
        except Exception as exc:
            frag = {"error": str(exc)}

        try:
            doc = bench_document_fts(exp, q)
        except Exception as exc:
            doc = {"error": str(exc)}

        comparisons.append({
            "query": q,
            "fragment_fts": frag,
            "document_fts": doc,
        })

        if "error" not in frag and "error" not in doc:
            print(
                f"{q[:34]:34} "
                f"{frag['median_ms']:10.2f} "
                f"{doc['median_ms']:10.2f} "
                f"{frag['unique_docs']:11d} "
                f"{doc['unique_docs']:10d}"
            )
        else:
            print(f"{q[:34]:34} ERROR")

    prod.close()
    exp.close()

    report = {
        "root": str(root),
        "catalog": str(catalog),
        "experiment_db": str(exp_db),
        "build": stats,
        "comparisons": comparisons,
    }

    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print()
    print("3/3 Verificación")
    print(f"  reporte: {report_path}")
    print("  producción modificada: NO")
    print("  Qdrant modificado:      NO")
    print("  Knowledge modificado:   NO")
    print("  PDFs leídos:            NO")
    print()

    if args.keep:
        print(f"Base experimental conservada: {exp_db}")
    else:
        print("La base experimental se conservará por ahora para poder inspeccionarla.")
        print("Podés borrarla manualmente después de la comparación.")

    print()
    print("FIN DEL EXPERIMENTO")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
