#!/usr/bin/env python3
"""Read-only timing of the Windows home and Standards data providers."""
from __future__ import annotations

import argparse
import json
import os
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


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--probe", choices=[item[1] for item in PROBES])
    parser.add_argument("--timeout", type=float, default=10.0)
    args = parser.parse_args()
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
