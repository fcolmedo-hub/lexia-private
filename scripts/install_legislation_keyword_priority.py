#!/usr/bin/env python3
"""Instala la prioridad normativa sin reemplazar otros cambios locales."""
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

BASE = "7b0dd1fd9484a9bb0108d1510ba28246d304a3d4"
SERVER = "app/ui2/server.py"
HELPER = "app/ui2/legislation_intent.py"


def git(root: Path, *arguments: str) -> bytes:
    result = subprocess.run(["git", *arguments], cwd=root, capture_output=True)
    if result.returncode:
        raise ValueError(result.stderr.decode("utf-8", errors="replace").strip() or "No se pudo leer la revisión.")
    return result.stdout


def patch_server(current: str, patch: bytes) -> str:
    if not patch:
        raise ValueError("La revisión no contiene la actualización normativa.")
    with tempfile.TemporaryDirectory(prefix="lexia-normas-comprobacion-") as folder:
        root = Path(folder)
        path = root / SERVER
        path.parent.mkdir(parents=True)
        path.write_text(current, encoding="utf-8", newline="\n")
        command = ["git", "apply", "--no-index", "--check", "-"]
        check = subprocess.run(command, cwd=root, input=patch, capture_output=True)
        if check.returncode:
            reverse = subprocess.run(["git", "apply", "--no-index", "--reverse", "--check", "-"], cwd=root, input=patch, capture_output=True)
            if reverse.returncode == 0:
                return current
            raise ValueError("Los cambios locales del buscador se cruzan con esta actualización. No se modificó LexIA.")
        applied = subprocess.run(["git", "apply", "--no-index", "-"], cwd=root, input=patch, capture_output=True)
        if applied.returncode:
            raise ValueError("No se pudo preparar el cambio del buscador.")
        return path.read_text(encoding="utf-8")


def prepare(root: Path, source: str) -> list[tuple[Path, bytes | None, bytes]]:
    revision = git(root, "rev-parse", "--verify", "--end-of-options", source + "^{commit}").decode().strip()
    patch = git(root, "diff", "--no-ext-diff", "--no-textconv", "--binary", BASE, revision, "--", SERVER)
    helper = git(root, "show", f"{revision}:{HELPER}").decode("utf-8-sig").replace("\r\n", "\n")
    ast.parse(helper)
    plan = []
    for name in (SERVER, HELPER):
        path = root / name
        if path.is_symlink():
            raise ValueError(f"No se admite un enlace simbólico: {name}")
        if any((root / parent).is_symlink() for parent in Path(name).parents):
            raise ValueError(f"No se admite una carpeta enlazada: {name}")
        if path.exists() and not path.is_file():
            raise ValueError(f"No es un archivo regular: {name}")
        if name == SERVER and not path.is_file():
            raise ValueError(f"Falta {name}.")
        original = path.read_bytes() if path.exists() else None
        decoded = original.decode("utf-8-sig") if original is not None else ""
        current = decoded.replace("\r\n", "\n")
        if name == SERVER:
            updated = patch_server(current, patch)
        else:
            if current and current != helper:
                raise ValueError(f"{name}: ya existe una versión local diferente.")
            updated = helper
        ast.parse(updated)
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
        with tempfile.NamedTemporaryFile(dir=path.parent, prefix="lexia-normas-", suffix=".tmp", delete=False) as stream:
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
    backup = parent / ("lexia-normas-" + datetime.now().strftime("%Y%m%d-%H%M%S-%f"))
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
            print("La prioridad normativa ya está instalada. No se modificó LexIA.")
        elif args.check:
            print("Comprobación correcta. Archivos por actualizar:")
            for path, _original, _data in plan:
                print("-", path.relative_to(root))
        else:
            backup = apply_plan(root, plan)
            print(f"Prioridad normativa instalada. Respaldo: {backup}")
            print("Cerrá LexIA completamente y volvé a abrirla.")
        return 0
    except (OSError, ValueError, UnicodeError, SyntaxError) as exc:
        print(f"No se pudo instalar la prioridad normativa: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
