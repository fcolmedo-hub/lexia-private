#!/usr/bin/env python3
"""Actualiza las fechas del navegador conservando las modificaciones locales."""
from __future__ import annotations

import argparse
import ast
from datetime import datetime
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys
import tempfile


BASE = "400a1013e493438d6c898a9a55bb6861e97fd691"
SERVER = "app/ui2/server.py"
NAVIGATOR = "app/ui2/navigator_3_3_4a.js"
DATES = "services/file_creation_dates.py"


def git_text(root: Path, revision: str, name: str) -> str:
    result = subprocess.run(["git", "show", f"{revision}:{name}"], cwd=root, capture_output=True)
    if result.returncode:
        raise ValueError(f"No se pudo leer {name} en {revision}.")
    return result.stdout.decode("utf-8-sig").replace("\r\n", "\n")


def block(text: str, start: str, end: str) -> str:
    if text.count(start) != 1 or text.count(end) != 1:
        raise ValueError("No se encontró un bloque único de navegación.")
    first, last = text.index(start), text.index(end)
    if last <= first:
        raise ValueError("La estructura de navegación es diferente.")
    return text[first:last]


def replace_block(current: str, before: str, after: str) -> str:
    if before == after:
        raise ValueError("La revisión no contiene la actualización de fechas.")
    if current.count(after) == 1:
        return current
    if current.count(before) != 1:
        raise ValueError("El bloque que se actualizará tiene cambios locales diferentes.")
    return current.replace(before, after, 1)


def patched_text(name: str, current: str, before: str, after: str) -> str:
    if name == SERVER:
        start, end = "def _navigator_browse_documents(", "\ndef _navigator_document_preview("
        updated = replace_block(current, block(before, start, end), block(after, start, end))
    elif name == NAVIGATOR:
        updated = current
        for start, end in [
            ("  const date=value=>{", "  const post=async"),
            ("        '<div class=\"result-meta\">'", "      '</div>'+\n      '<button type=\"button\" class=\"lexia-nav-file-menu-trigger\""),
        ]:
            updated = replace_block(updated, block(before, start, end), block(after, start, end))
    elif name == DATES:
        if current and current != after:
            raise ValueError("Ya existe un servicio de fechas diferente.")
        updated = after
    else:
        raise ValueError("Archivo fuera del alcance del instalador.")
    if name.endswith(".py"):
        ast.parse(updated)
    return updated


def prepare(root: Path, source: str) -> list[tuple[Path, bytes | None, bytes]]:
    plan = []
    for name in (SERVER, NAVIGATOR, DATES):
        path = root / name
        if path.is_symlink() or (path.exists() and not path.is_file()):
            raise ValueError(f"No es un archivo regular: {name}")
        if name != DATES and not path.is_file():
            raise ValueError(f"Falta {name}.")
        original = path.read_bytes() if path.exists() else None
        decoded = original.decode("utf-8-sig") if original is not None else ""
        current = decoded.replace("\r\n", "\n")
        before = git_text(root, BASE, name) if name != DATES else ""
        after = git_text(root, source, name)
        try:
            updated = patched_text(name, current, before, after)
        except (ValueError, SyntaxError) as exc:
            raise ValueError(f"{name}: {exc}") from exc
        if updated == current:
            continue
        newline = "\r\n" if decoded.count("\r\n") > decoded.count("\n") / 2 else "\n"
        bom = "\ufeff" if original and original.startswith(b"\xef\xbb\xbf") else ""
        data = (bom + updated.replace("\n", newline)).encode("utf-8")
        plan.append((path, original, data))
    return plan


def atomic_write(path: Path, data: bytes, mode: int = 0o644) -> None:
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, prefix="lexia-fechas-", suffix=".tmp", delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(data)
        os.chmod(temporary, mode)
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def apply_plan(root: Path, plan: list) -> Path | None:
    if not plan:
        return None
    for path, original, _data in plan:
        actual = path.read_bytes() if path.exists() else None
        if actual != original:
            raise ValueError(f"El archivo cambió durante la comprobación: {path}")
    parent = Path.home() / "Desktop"
    if not parent.is_dir():
        parent = Path.home()
    backup = parent / ("lexia-fechas-" + datetime.now().strftime("%Y%m%d-%H%M%S-%f"))
    backup.mkdir()
    manifest, modes = {}, {}
    for path, original, _data in plan:
        name = str(path.relative_to(root))
        manifest[name] = {"existed": original is not None}
        modes[path] = stat.S_IMODE(path.stat().st_mode) if original is not None else 0o644
        if original is not None:
            saved = backup / name
            saved.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, saved)
    (backup / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    written = []
    try:
        for path, original, data in plan:
            atomic_write(path, data, modes[path])
            written.append((path, original))
    except OSError:
        for path, original in reversed(written):
            if original is None:
                path.unlink(missing_ok=True)
            else:
                atomic_write(path, original, modes[path])
        raise
    return backup


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, help="Revisión publicada que se instalará")
    parser.add_argument("--check", action="store_true", help="Comprobar sin escribir")
    args = parser.parse_args()
    root = Path.cwd()
    try:
        plan = prepare(root, args.source)
        if not plan:
            print("Las fechas de creación ya están instaladas. No se modificó LexIA.")
        elif args.check:
            print("Comprobación correcta. Archivos por actualizar:")
            for path, _original, _data in plan:
                print("-", path.relative_to(root))
        else:
            backup = apply_plan(root, plan)
            print(f"Fechas de creación instaladas. Respaldo: {backup}")
            print("Cerrá LexIA completamente y volvé a abrirla.")
        return 0
    except (OSError, ValueError, UnicodeError, SyntaxError) as exc:
        print(f"No se pudo instalar la actualización de fechas: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
