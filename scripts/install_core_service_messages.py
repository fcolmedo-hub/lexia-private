#!/usr/bin/env python3
"""Corrige los avisos del servicio interno conservando los cambios locales."""
import argparse
import ast
from datetime import datetime
import os
from pathlib import Path
import shutil
import stat
import sys
import tempfile


SERVER = "app/ui2/server.py"
REPLACEMENTS = (
    ('"La interfaz clásica de LexIA debe permanecer abierta para eliminar. "\n            "No se encontró su puente local de borrado seguro.",',
     '"El servicio interno de LexIA no está disponible. "\n            "Cerrá LexIA por completo y volvé a abrirla.",', 2),
    ("El puente de la interfaz clásica respondió incorrectamente.",
     "El servicio interno de LexIA respondió incorrectamente.", 1),
    ("Eliminar usa el servicio vivo de la interfaz clásica. Sin AutoSync secundario.",
     "Las operaciones de UI2 usan el servicio interno de LexIA.", 1),
)


def prepare(original: bytes) -> bytes:
    text = original.decode("utf-8-sig")
    newline = "\r\n" if text.count("\r\n") > text.count("\n") / 2 else "\n"
    text = text.replace("\r\n", "\n")
    updated = original
    for before, after, expected in REPLACEMENTS:
        old_count, new_count = text.count(before), text.count(after)
        if old_count == 0 and new_count == expected:
            continue
        if old_count != expected or new_count:
            raise ValueError("Los avisos tienen cambios locales diferentes. No se modificó LexIA.")
        text = text.replace(before, after)
        updated = updated.replace(before.replace("\n", newline).encode("utf-8"), after.replace("\n", newline).encode("utf-8"))
    ast.parse(text)
    if updated.decode("utf-8-sig").replace("\r\n", "\n") != text:
        raise ValueError("El archivo tiene saltos de línea diferentes en los avisos.")
    return updated


def install(path: Path, original: bytes, updated: bytes) -> Path:
    if path.read_bytes() != original:
        raise ValueError("El archivo cambió durante la comprobación.")
    parent = Path.home() / "Desktop"
    if not parent.is_dir():
        parent = Path.home()
    backup = parent / ("lexia-avisos-" + datetime.now().strftime("%Y%m%d-%H%M%S-%f"))
    backup.mkdir()
    shutil.copy2(path, backup / "server.py")
    mode = stat.S_IMODE(path.stat().st_mode)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, prefix="lexia-avisos-", delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(updated)
        os.chmod(temporary, mode)
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return backup


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Comprobar sin escribir")
    args = parser.parse_args()
    path = Path.cwd() / SERVER
    try:
        if path.is_symlink() or any(parent.is_symlink() for parent in path.parents) or not path.is_file():
            raise ValueError("No se encontró un servidor regular de LexIA en esta carpeta.")
        original = path.read_bytes()
        updated = prepare(original)
        if updated == original:
            print("Los avisos del servicio interno ya están actualizados.")
        elif args.check:
            print("Comprobación correcta. Se actualizarán sólo los avisos de app/ui2/server.py.")
        else:
            backup = install(path, original, updated)
            print(f"Avisos actualizados. Respaldo: {backup}")
            print("Cerrá LexIA por completo y volvé a abrirla.")
        return 0
    except (OSError, UnicodeError, ValueError, SyntaxError) as exc:
        print(f"No se pudo instalar la corrección: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
