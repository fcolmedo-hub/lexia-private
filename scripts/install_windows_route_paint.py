#!/usr/bin/env python3
"""Install only the Windows Investigation/Maintenance first-paint UI changes."""

from __future__ import annotations

import argparse
from datetime import datetime
import os
from pathlib import Path
import shutil
import subprocess


BASE = "29b1647f42e64bcfcd766864d01b043ad48074b9"
MAINTENANCE_BEFORE = "2b1ee3b592db08c997c4bc463f34546a16d82495"
FILES = (
    "app/ui2/assets/maintenance.js",
    "app/ui2/assets/app_runtime.js",
    "app/ui2/assets/windows_live_badge_cleanup.js",
)


def git(*args: str, cwd: Path | None = None) -> bytes:
    process = subprocess.run(
        ["git", *args], cwd=cwd, capture_output=True, check=False
    )
    if process.returncode:
        raise RuntimeError(process.stderr.decode("utf-8", errors="replace").strip())
    return process.stdout


def normalized(raw: bytes) -> str:
    return raw.decode("utf-8").replace("\r\n", "\n")


def maintain_newlines(source: bytes, text: str) -> bytes:
    if source.count(b"\r\n") > source.count(b"\n") - source.count(b"\r\n"):
        text = text.replace("\n", "\r\n")
    return text.encode("utf-8")


def first_state_block(text: str) -> str:
    start = text.find("    if(!state){\n")
    if start < 0:
        raise ValueError("No se encontró el bloque inicial de Mantenimiento.")
    end_marker = "      return;\n    }"
    end = text.find(end_marker, start)
    if end < 0:
        raise ValueError("No se pudo delimitar el bloque inicial de Mantenimiento.")
    return text[start : end + len(end_marker)]


def prepare(path: str, current: bytes, before: bytes, after: bytes) -> bytes:
    local = normalized(current)
    old = normalized(before)
    new = normalized(after)
    if path.endswith("/maintenance.js"):
        old_block = first_state_block(old)
        new_block = first_state_block(new)
        if new_block in local:
            return current
        if local.count(old_block) != 1:
            raise ValueError(
                "El bloque inicial de maintenance.js tiene cambios propios; "
                "se necesita revisarlo antes de instalar."
            )
        return maintain_newlines(current, local.replace(old_block, new_block, 1))
    if local == new:
        return current
    if local != old:
        raise ValueError(
            f"{path} tiene cambios locales distintos de la versión conocida."
        )
    return maintain_newlines(current, new)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Simular sin escribir")
    args = parser.parse_args(argv)

    root = Path(git("rev-parse", "--show-toplevel").decode().strip())
    git("merge-base", "--is-ancestor", BASE, "FETCH_HEAD", cwd=root)
    changes: dict[str, bytes] = {}
    for path in FILES:
        current_path = root / path
        if not current_path.is_file():
            raise SystemExit(f"Falta {path}. No se modificó ningún archivo.")
        current = current_path.read_bytes()
        before_ref = MAINTENANCE_BEFORE if path.endswith("/maintenance.js") else BASE
        before = git("show", f"{before_ref}:{path}", cwd=root)
        after_ref = BASE if path.endswith("/maintenance.js") else "FETCH_HEAD"
        after = git("show", f"{after_ref}:{path}", cwd=root)
        try:
            candidate = prepare(path, current, before, after)
        except (ValueError, UnicodeError) as exc:
            raise SystemExit(f"Conflicto en {path}: {exc}\nNo se modificó ningún archivo.") from exc
        if candidate != current:
            changes[path] = candidate
        print(f"{path}: {'pendiente' if path in changes else 'ya instalado'}")

    if args.check or not changes:
        print("Comprobación correcta. No se modificó ningún archivo.")
        return

    desktop = Path.home() / "Desktop"
    parent = desktop if desktop.is_dir() else Path.home()
    backup = parent / ("lexia-pantallas-windows-" + datetime.now().strftime("%Y%m%d-%H%M%S-%f"))
    backup.mkdir()
    for path in changes:
        destination = backup / path
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(root / path, destination)
    try:
        for path, data in changes.items():
            (root / path).write_bytes(data)
    except OSError:
        for path in changes:
            shutil.copy2(backup / path, root / path)
        raise
    print(f"Instalación terminada. Respaldo: {backup}")
    print("Cerrá LexIA por completo y volvé a abrirla. No hace falta reconstruir el .exe.")


if __name__ == "__main__":
    main()
