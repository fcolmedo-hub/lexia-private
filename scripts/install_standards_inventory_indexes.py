#!/usr/bin/env python3
"""Crea índices de recuento en Estándares con respaldo y sin cambiar filas."""
from __future__ import annotations

import argparse
from contextlib import closing
from datetime import datetime
import os
from pathlib import Path
import shutil
import sqlite3
import sys
import time


INDEXES = (
    ("idx_standards_visibility_uid", "standards",
     ("publication_status", "review_status", "standard_uid")),
    ("idx_canonical_status_uid", "canonical_standards",
     ("status", "canonical_uid")),
    ("idx_occurrences_canonical_standard", "standard_occurrences",
     ("canonical_uid", "standard_uid")),
    ("idx_quotes_valid_standard", "quotes", ("standard_uid",)),
)


def database(root: Path, specified: str | None) -> Path:
    if specified:
        return Path(specified).expanduser().resolve()
    runtime = Path(os.environ.get("LEXIA_RUNTIME_PATH") or root / "runtime").expanduser()
    return runtime / "standards" / "standards.sqlite3"


def inspect(con: sqlite3.Connection) -> list[tuple[str, str, tuple[str, ...]]]:
    missing = []
    for name, table, columns in INDEXES:
        actual_columns = {row[1] for row in con.execute(f'PRAGMA table_info("{table}")')}
        if not set(columns).issubset(actual_columns):
            raise ValueError(f"Faltan columnas de {table}: {', '.join(set(columns)-actual_columns)}")
        existing = con.execute(
            "SELECT type, sql FROM sqlite_master WHERE name=?", (name,)
        ).fetchone()
        if existing:
            if existing[0] != "index":
                raise ValueError(f"{name} existe, pero no es un índice")
            actual = tuple(row[2] for row in con.execute(f'PRAGMA index_info("{name}")'))
            if actual != columns:
                raise ValueError(f"{name} existe con columnas diferentes: {actual}")
            if name == "idx_quotes_valid_standard" and "TRIM(quote_text)<>'' AND page_start>0" not in (existing[1] or ""):
                raise ValueError(f"{name} existe con una condición diferente")
        else:
            missing.append((name, table, columns))
    return missing


def apply(db: Path, missing: list[tuple[str, str, tuple[str, ...]]]) -> Path:
    minimum = 2 * db.stat().st_size + 20 * 1024 * 1024
    if shutil.disk_usage(db.parent).free < minimum:
        raise OSError("No hay espacio suficiente para el respaldo y los índices")
    backup = db.with_name(
        "standards-antes-indices-" + datetime.now().strftime("%Y%m%d-%H%M%S-%f") + ".sqlite3"
    )
    started = time.monotonic()
    backup_complete = False
    try:
        with closing(sqlite3.connect(db, timeout=15)) as source:
            with closing(sqlite3.connect(backup)) as destination:
                source.backup(destination)
                destination.commit()
        backup_complete = True
        with closing(sqlite3.connect(db, timeout=15)) as con:
            before = con.execute("SELECT COUNT(*) FROM standards").fetchone()[0]
            con.execute("BEGIN IMMEDIATE")
            try:
                for name, table, columns in missing:
                    condition = (" WHERE TRIM(quote_text)<>'' AND page_start>0"
                                 if name == "idx_quotes_valid_standard" else "")
                    con.execute(
                        f'CREATE INDEX "{name}" ON "{table}" ('
                        + ", ".join(f'"{column}"' for column in columns) + ")" + condition
                    )
                if inspect(con):
                    raise RuntimeError("La verificación de los índices no terminó")
                after = con.execute("SELECT COUNT(*) FROM standards").fetchone()[0]
                if before != after:
                    raise RuntimeError("Cambió el número de estándares; se revierte la operación")
                con.commit()
            except BaseException:
                con.rollback()
                raise
    except BaseException:
        if not backup_complete:
            backup.unlink(missing_ok=True)
        elif backup.exists():
            print(f"Respaldo disponible: {backup}", file=sys.stderr)
        raise
    print(f"Índices creados en {time.monotonic()-started:.1f} s; estándares: {after}.")
    return backup


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--db", help="Base SQLite para una prueba aislada")
    args = parser.parse_args()
    db = database(Path.cwd(), args.db)
    try:
        if not db.is_file() or db.is_symlink():
            raise ValueError(f"No se encontró una base regular de Estándares: {db}")
        uri = db.resolve().as_uri() + "?mode=ro"
        with closing(sqlite3.connect(uri, uri=True, timeout=3)) as con:
            missing = inspect(con)
        print(f"Base: {db} | tamaño: {db.stat().st_size / 1048576:.1f} MiB")
        print("Índices pendientes: " + (", ".join(row[0] for row in missing) if missing else "ninguno"))
        if args.check or not missing:
            print("Comprobación de solo lectura terminada. No se modificó LexIA.")
            return 0
        backup = apply(db, missing)
        print(f"Respaldo: {backup}")
        print("Cerrá LexIA completamente y volvé a abrirla.")
        return 0
    except (OSError, ValueError, RuntimeError, sqlite3.Error) as exc:
        print(f"No se completó la actualización: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
