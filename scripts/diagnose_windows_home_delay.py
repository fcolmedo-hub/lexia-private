#!/usr/bin/env python3
"""Read-only timing of the Windows home and Standards data providers."""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import subprocess
import sys
import time
from pathlib import Path

PROBES = (
    ("catalogo", "catalog"),
    ("investigaciones", "contexts"),
    ("busquedas", "searches"),
    ("cola OCR", "ocr"),
    ("inventario estandares", "standards"),
)


def probe(name: str) -> int:
    root = Path.cwd()
    start = time.perf_counter()
    sys.path.insert(0, str(root))
    sys.path.insert(0, str(root / "app" / "ui2"))
    if name == "standards":
        from services.standards_service import StandardsService

        service = StandardsService()
        imported = time.perf_counter()
        print(f"Importación: {imported - start:.2f} s", flush=True)
        result = service.inventory()
    else:
        os.environ["LEXIA_UI2_LIVE_CACHE_SECONDS"] = "30"
        from backend import LiveReadOnlyAdapter

        adapter = LiveReadOnlyAdapter()
        imported = time.perf_counter()
        print(f"Importación: {imported - start:.2f} s", flush=True)
        if name == "catalog":
            result = adapter._catalog()
        elif name == "contexts":
            result = adapter._generic_history(adapter.context_history_path, 5)
        elif name == "searches":
            result = adapter._generic_history(adapter.search_history_path, 5)
        elif name == "ocr":
            result = adapter._ocr_stats()
        else:
            raise ValueError(name)
    print(f"Consulta: {time.perf_counter() - imported:.2f} s", flush=True)
    print(json.dumps({key: value for key, value in result.items()
                      if key in {"documents", "count", "error", "pending", "processing", "visible_canonical_standards"}},
                     ensure_ascii=False, default=str)[:600], flush=True)
    return 0


def catalog_sql() -> int:
    root = Path.cwd()
    sys.path.insert(0, str(root))
    sys.path.insert(0, str(root / "app" / "ui2"))
    os.environ["LEXIA_UI2_LIVE_CACHE_SECONDS"] = "30"
    from backend import LiveReadOnlyAdapter

    adapter = LiveReadOnlyAdapter()
    print(f"Caché de Inicio: {getattr(adapter, 'live_cache_seconds', 'sin soporte')} s | "
          f"recuento diferido de fragmentos: {hasattr(adapter, '_deferred_fragment_count')}", flush=True)
    if not hasattr(adapter, '_deferred_fragment_count'):
        print("La versión instalada aún calcula fragmentos antes de mostrar Inicio.", flush=True)
        return 0
    uri = adapter.catalog_path.resolve().as_uri() + "?mode=ro"
    con = sqlite3.connect(uri, uri=True, timeout=3)
    con.execute("PRAGMA query_only=ON")
    statements = (
        ("documentos", "SELECT COUNT(*) FROM documents WHERE is_deleted=0"),
        ("agregados hoy", "SELECT COUNT(*) FROM documents WHERE is_deleted=0 AND created_at IS NOT NULL AND date(created_at, 'localtime')=date('now', 'localtime')"),
        ("categorias", "SELECT category,COUNT(*) FROM documents WHERE is_deleted=0 GROUP BY category ORDER BY COUNT(*) DESC LIMIT 8"),
        ("documentos recientes", "SELECT name,path,category,updated_at,extraction_method,total_pages FROM documents WHERE is_deleted=0 AND (extraction_error IS NULL OR extraction_error='') ORDER BY updated_at DESC LIMIT 8"),
        ("errores recientes", "SELECT name,path,category,updated_at,extraction_error FROM documents WHERE is_deleted=0 AND extraction_error IS NOT NULL AND extraction_error!='' ORDER BY updated_at DESC LIMIT 6"),
        ("paginas OCR", "SELECT COALESCE(SUM(ocr_pages),0) FROM documents WHERE is_deleted=0"),
    )
    try:
        for index, (label, sql) in enumerate(statements):
            if index == 2:
                start = time.perf_counter()
                adapter._deferred_fragment_count()
                print(f"Recuento de fragmentos lanzado en segundo plano: {time.perf_counter()-start:.2f} s", flush=True)
            start = time.perf_counter()
            print(f"INICIO {label}", flush=True)
            con.set_progress_handler(lambda: int(time.perf_counter()-start > 7), 20000)
            try:
                rows = con.execute(sql).fetchall()
                print(f"FIN {label}: {time.perf_counter()-start:.2f} s | filas: {len(rows)}", flush=True)
            except sqlite3.Error as exc:
                print(f"ERROR {label}: {time.perf_counter()-start:.2f} s | {exc}", flush=True)
            finally:
                con.set_progress_handler(None, 0)
    finally:
        con.close()
    return 0


def standards_sql() -> int:
    root = Path.cwd()
    sys.path.insert(0, str(root))
    from services.standards_service import StandardsService, _canonical_ready

    service = StandardsService()
    if not service.available():
        print("No existe el catálogo de Estándares en la ruta configurada.", flush=True)
        return 0
    uri = service.db_path.resolve().as_uri() + "?mode=ro"
    con = sqlite3.connect(uri, uri=True, timeout=3)
    con.execute("PRAGMA query_only=ON")
    visibility = service._base_visibility_sql()
    statements = [
        ("incidencias", "SELECT COUNT(*) FROM standards"),
        ("incidencias activas", "SELECT COUNT(*) FROM standards WHERE review_status<>'rejected'"),
        ("incidencias visibles", "SELECT COUNT(*) FROM standards s WHERE " + visibility),
        ("avisos de evidencia", "SELECT COUNT(*) FROM standards s WHERE " + visibility
         + " AND (s.publication_status='blocked' OR " + service._incomplete_evidence_sql() + ")"),
    ]
    if _canonical_ready(con):
        statements.extend([
            ("canonicos confirmados", "SELECT COUNT(*) FROM canonical_standards WHERE status='confirmed'"),
            ("canonicos visibles", """SELECT COUNT(*) FROM canonical_standards c
                WHERE c.status='confirmed' AND EXISTS(
                    SELECT 1 FROM standard_occurrences o
                    JOIN standards s ON s.standard_uid=o.standard_uid
                    WHERE o.canonical_uid=c.canonical_uid
                      AND s.review_status<>'rejected'
                      AND s.publication_status IN ('ready','published','blocked'))"""),
        ])
    try:
        for label, sql in statements:
            started = time.perf_counter()
            print(f"INICIO {label}", flush=True)
            con.set_progress_handler(lambda: int(time.perf_counter()-started > 7), 20000)
            try:
                value = con.execute(sql).fetchone()[0]
                print(f"FIN {label}: {time.perf_counter()-started:.2f} s | total: {value}", flush=True)
            except sqlite3.Error as exc:
                print(f"ERROR {label}: {time.perf_counter()-started:.2f} s | {exc}", flush=True)
            finally:
                con.set_progress_handler(None, 0)
    finally:
        con.close()
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--probe", choices=[item[1] for item in PROBES])
    parser.add_argument("--timeout", type=float, default=10.0)
    parser.add_argument("--catalog-sql", action="store_true")
    parser.add_argument("--standards-sql", action="store_true")
    args = parser.parse_args()
    if args.catalog_sql:
        return catalog_sql()
    if args.standards_sql:
        return standards_sql()
    if args.probe:
        return probe(args.probe)
    if not (Path.cwd() / "app" / "ui2" / "backend.py").exists():
        parser.error("Ejecutá este diagnóstico desde la carpeta D:\\LexIA_2.3_DEV")
    print("Medición de solo lectura; no modifica el catálogo ni los estándares.", flush=True)
    for label, name in PROBES:
        began = time.perf_counter()
        try:
            result = subprocess.run(
                [sys.executable, __file__, "--probe", name],
                cwd=Path.cwd(), capture_output=True, text=True,
                encoding="utf-8", errors="replace", timeout=args.timeout,
            )
            output = result.stdout.strip().replace("\n", " | ")
            error = result.stderr.strip().splitlines()[-1:] if result.stderr else []
            print(f"{label}: {time.perf_counter() - began:.1f} s | {output}"
                  + (f" | ERROR {error[0]}" if error else ""), flush=True)
        except subprocess.TimeoutExpired as exc:
            output = (exc.stdout or b"")
            if isinstance(output, bytes):
                output = output.decode("utf-8", errors="replace")
            print(f"{label}: >{args.timeout:.0f} s | TIEMPO AGOTADO"
                  + (f" | {output.strip().replace(chr(10), ' | ')}" if output else ""), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
