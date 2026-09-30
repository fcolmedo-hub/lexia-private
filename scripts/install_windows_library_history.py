#!/usr/bin/env python3
"""Restituye Agregados hoy en Biblioteca sin recorrer el catálogo al abrir Inicio."""
from __future__ import annotations

import argparse
from contextlib import closing
from datetime import datetime
import difflib
import os
from pathlib import Path
import re
import shutil
import sqlite3
import subprocess
import sys
import tempfile


BASE = "69d251202fefe027261bd77a90cadddf2c02d7d0"
PATH = "app/ui2/backend.py"
INDEX = "idx_documents_active_created_at"


def source_at(revision: str) -> str:
    return subprocess.check_output(
        ["git", "show", f"{revision}:{PATH}"], stderr=subprocess.PIPE
    ).decode("utf-8-sig")


def merge(local: str, base: str, target: str) -> str:
    old, new = base.splitlines(keepends=True), target.splitlines(keepends=True)
    result = local
    edits = [op for op in difflib.SequenceMatcher(None, old, new,
                                                   autojunk=False).get_opcodes()
             if op[0] != "equal"]
    if not edits:
        raise ValueError("La revisión descargada no contiene esta corrección")
    # Nearby edits can change each other's context; apply them as one hunk.
    hunks = []
    for _, i1, i2, j1, j2 in edits:
        if hunks and i1 - hunks[-1][1] <= 4:
            first, _, start, _ = hunks[-1]
            hunks[-1] = (first, i2, start, j2)
        else:
            hunks.append((i1, i2, j1, j2))
    for i1, i2, j1, j2 in hunks:
        before, after = old[max(0, i1 - 2):i1], old[i2:min(len(old), i2 + 2)]
        previous = "".join(before + old[i1:i2] + after)
        replacement = "".join(before + new[j1:j2] + after)
        if result.count(previous) == 1:
            result = result.replace(previous, replacement, 1)
        elif result.count(replacement) == 1:
            continue
        else:
            raise ValueError("La consulta local difiere en una zona que debe actualizarse; no se modificó LexIA")
    compile(result, PATH, "exec")
    return result


def index_missing(connection: sqlite3.Connection) -> bool:
    columns = {row[1] for row in connection.execute('PRAGMA table_info("documents")')}
    if not {"created_at", "is_deleted"}.issubset(columns):
        raise ValueError("La tabla documents no tiene created_at e is_deleted")
    row = connection.execute(
        "SELECT type,sql FROM sqlite_master WHERE name=?", (INDEX,)
    ).fetchone()
    if row is None:
        return True
    if row[0] != "index":
        raise ValueError(f"{INDEX} existe con otro tipo")
    indexed = tuple(item[2] for item in connection.execute(f'PRAGMA index_info("{INDEX}")'))
    if indexed != ("created_at",) or not re.search(
        r"\bWHERE\s+is_deleted\s*=\s*0\b", row[1] or "", re.IGNORECASE
    ):
        raise ValueError(f"{INDEX} ya existe con una definición distinta")
    return False


def install_index(db: Path) -> None:
    if shutil.disk_usage(db.parent).free < 64 * 1024 * 1024:
        raise OSError("Se requieren al menos 64 MiB libres para crear el índice")
    with closing(sqlite3.connect(db, timeout=30)) as con:
        if not index_missing(con):
            return
        con.execute("BEGIN IMMEDIATE")
        try:
            before = con.execute(
                "SELECT COUNT(*) FROM documents WHERE is_deleted=0"
            ).fetchone()[0]
            con.execute(
                f'CREATE INDEX "{INDEX}" ON documents(created_at) WHERE is_deleted=0'
            )
            if index_missing(con):
                raise RuntimeError("No se pudo verificar el índice")
            after = con.execute(
                "SELECT COUNT(*) FROM documents WHERE is_deleted=0"
            ).fetchone()[0]
            if before != after:
                raise RuntimeError("Cambió el número de documentos; se revierte la operación")
            con.commit()
        except BaseException:
            con.rollback()
            raise
    print(f"Índice de creación instalado. Documentos activos: {after}.")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, help="Commit descargado que contiene la corrección")
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--db", help="Ruta del catálogo, si no está en runtime/lexia_catalog.sqlite3")
    args = parser.parse_args()
    if not re.fullmatch(r"[0-9a-f]{40}", args.source):
        parser.error("--source debe ser un SHA completo de 40 caracteres")
    path = Path.cwd() / PATH
    db = Path(args.db).expanduser().resolve() if args.db else Path.cwd() / "runtime" / "lexia_catalog.sqlite3"
    try:
        if not path.is_file() or path.is_symlink():
            raise ValueError(f"No se encontró el archivo regular {path}")
        if not db.is_file() or db.is_symlink():
            raise ValueError(f"No se encontró el catálogo regular {db}")
        original = path.read_text(encoding="utf-8-sig")
        updated = merge(original, source_at(BASE), source_at(args.source))
        uri = db.resolve().as_uri() + "?mode=ro"
        with closing(sqlite3.connect(uri, uri=True, timeout=3)) as con:
            missing = index_missing(con)
        print(f"Catálogo: {db} | índice de fecha pendiente: {'sí' if missing else 'no'}")
        if updated == original and not missing:
            print("El historial de Biblioteca ya está restituido.")
            return 0
        if args.check:
            print("Comprobación correcta: " + ("backend.py e índice" if updated != original and missing else "una actualización") + ". No se modificó LexIA.")
            return 0
        # SQLite CREATE INDEX is transactional and never updates document rows.
        if missing:
            install_index(db)
        temporary = None
        if updated != original:
            backup = path.with_name(path.name + ".respaldo-" + datetime.now().strftime("%Y%m%d-%H%M%S-%f"))
            shutil.copy2(path, backup)
            try:
                with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", newline="\n",
                                                 prefix=path.name + ".", suffix=".tmp",
                                                 dir=path.parent, delete=False) as stream:
                    temporary = Path(stream.name)
                    stream.write(updated)
                os.replace(temporary, path)
            finally:
                if temporary is not None:
                    temporary.unlink(missing_ok=True)
            print(f"Historial de Biblioteca restituido. Respaldo del archivo: {backup}")
        print("Cerrá LexIA completamente y volvé a abrirla para ver Agregados hoy.")
        return 0
    except (OSError, ValueError, UnicodeError, RuntimeError, sqlite3.Error, subprocess.CalledProcessError) as exc:
        print(f"No se completó la actualización: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
