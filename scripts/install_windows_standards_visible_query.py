#!/usr/bin/env python3
"""Aplica la consulta rápida de Estándares conservando cambios locales ajenos."""
from __future__ import annotations

import argparse
from datetime import datetime
import difflib
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile


BASE = "f0a8e9be2770a8cb1a317b24330c956134e3eada"
PATH = "services/standards_service.py"


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


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, help="Commit descargado que contiene la corrección")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    if not re.fullmatch(r"[0-9a-f]{40}", args.source):
        parser.error("--source debe ser un SHA completo de 40 caracteres")
    path = Path.cwd() / PATH
    try:
        if not path.is_file() or path.is_symlink():
            raise ValueError(f"No se encontró el archivo regular {path}")
        original = path.read_text(encoding="utf-8-sig")
        updated = merge(original, source_at(BASE), source_at(args.source))
        if updated == original:
            print("La consulta rápida de Estándares ya está instalada.")
            return 0
        if args.check:
            print("Comprobación correcta: 1 archivo por actualizar. No se modificó LexIA.")
            return 0
        backup = path.with_name(path.name + ".respaldo-" + datetime.now().strftime("%Y%m%d-%H%M%S-%f"))
        shutil.copy2(path, backup)
        temporary = None
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
        print(f"Consulta rápida instalada. Respaldo: {backup}")
        print("Cerrá LexIA completamente y volvé a abrirla.")
        return 0
    except (OSError, ValueError, UnicodeError, subprocess.CalledProcessError) as exc:
        print(f"No se modificó LexIA: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
