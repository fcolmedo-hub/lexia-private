#!/usr/bin/env python3
"""Install PR 24 over the Windows checkout with a complete three-way preflight."""

from __future__ import annotations

import argparse
from datetime import datetime
from difflib import SequenceMatcher
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile


BASE = "400a1013e493438d6c898a9a55bb6861e97fd691"
TARGET = "FETCH_HEAD"


def git(root: Path, *args: str) -> bytes:
    result = subprocess.run(["git", *args], cwd=root, capture_output=True)
    if result.returncode:
        raise RuntimeError(result.stderr.decode("utf-8", errors="replace").strip())
    return result.stdout


def decode(data: bytes) -> tuple[str, bool, bool]:
    bom = data.startswith(b"\xef\xbb\xbf")
    text = data.decode("utf-8-sig" if bom else "utf-8")
    crlf = text.count("\r\n") > text.count("\n") - text.count("\r\n")
    return text.replace("\r\n", "\n"), bom, crlf


def encode(text: str, bom: bool, crlf: bool) -> bytes:
    return (("\ufeff" if bom else "") + (text.replace("\n", "\r\n") if crlf else text)).encode("utf-8")


def merge(current: bytes, before: bytes, after: bytes) -> bytes:
    local, bom, crlf = decode(current)
    old = decode(before)[0]
    new = decode(after)[0]
    if local == new:
        return current
    if local == old:
        return encode(new, bom, crlf)
    with tempfile.TemporaryDirectory(prefix="lexia-merge-") as temporary:
        paths = [Path(temporary) / name for name in ("local", "base", "new")]
        for path, value in zip(paths, (local, old, new)):
            path.write_text(value, encoding="utf-8", newline="\n")
        result = subprocess.run(["git", "merge-file", "-p", *(str(path) for path in paths)], capture_output=True)
    if result.returncode == 0:
        return encode(result.stdout.decode("utf-8"), bom, crlf)
    if result.returncode != 1:
        raise RuntimeError(result.stderr.decode("utf-8", errors="replace"))
    # Git groups adjacent edits into a conflict even when they touch distinct
    # lines. Retry only when every edit occupies a disjoint base-line range.
    base_lines = old.splitlines(keepends=True)

    def edits(variant: str):
        lines = variant.splitlines(keepends=True)
        matcher = SequenceMatcher(None, base_lines, lines, autojunk=False)
        return [(start, end, lines[left:right]) for tag, start, end, left, right in matcher.get_opcodes() if tag != "equal"]

    local_edits = edits(local)
    target_edits = edits(new)
    for start, end, replacement in target_edits:
        for other_start, other_end, other_replacement in local_edits:
            same = (start, end, replacement) == (other_start, other_end, other_replacement)
            overlaps = max(start, other_start) < min(end, other_end)
            touches_insertion = (start == end and other_start <= start <= other_end) or (other_start == other_end and start <= other_start <= end)
            if (overlaps or touches_insertion) and not same:
                raise ValueError("Los cambios locales se cruzan con esta actualización; no se escribió ningún archivo.")
    all_edits = list(local_edits)
    for edit in target_edits:
        if edit not in all_edits:
            all_edits.append(edit)
    merged = []
    position = 0
    for start, end, replacement in sorted(all_edits, key=lambda item: (item[0], item[1])):
        merged.extend(base_lines[position:start])
        merged.extend(replacement)
        position = end
    merged.extend(base_lines[position:])
    return encode("".join(merged), bom, crlf)


def changes(root: Path, base: str = BASE, target: str = TARGET) -> dict[str, bytes]:
    git(root, "merge-base", "--is-ancestor", base, target)
    raw = git(root, "diff", "--name-status", "-z", "--diff-filter=AM", base, target, "--")
    fields = raw.decode("utf-8").split("\0")
    planned: dict[str, bytes] = {}
    conflicts: list[str] = []
    for status, name in zip(fields[0::2], fields[1::2]):
        if not name:
            continue
        if name == "app/ui2/index.html":
            raise RuntimeError("La actualización intenta modificar index.html; se detuvo.")
        path = root / name
        target_content = git(root, "show", f"{target}:{name}")
        if status == "A":
            if path.exists() and path.read_bytes() != target_content:
                conflicts.append(name + " (ya existe con otro contenido)")
            elif not path.exists():
                planned[name] = target_content
        else:
            if not path.is_file():
                conflicts.append(name + " (falta el archivo local)")
                continue
            try:
                candidate = merge(path.read_bytes(), git(root, "show", f"{base}:{name}"), target_content)
            except (UnicodeError, ValueError) as error:
                conflicts.append(name + " (" + str(error) + ")")
                continue
            if candidate != path.read_bytes():
                planned[name] = candidate
    if conflicts:
        raise ValueError("Conflictos detectados:\n- " + "\n- ".join(conflicts) + "\nNo se modificó tu instalación.")
    return planned


def install(root: Path, planned: dict[str, bytes]) -> Path:
    desktop = Path.home() / "Desktop"
    parent = desktop if desktop.is_dir() else Path.home()
    backup = parent / ("lexia-pr24-respaldo-" + datetime.now().strftime("%Y%m%d-%H%M%S-%f"))
    backup.mkdir()
    existing: set[str] = set()
    for name in planned:
        source = root / name
        if source.exists():
            existing.add(name)
            destination = backup / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)
    written: list[str] = []
    try:
        for name, data in planned.items():
            destination = root / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(dir=destination.parent, prefix=".lexia-install-", delete=False) as output:
                output.write(data)
                temp_name = output.name
            try:
                os.replace(temp_name, destination)
            finally:
                Path(temp_name).unlink(missing_ok=True)
            written.append(name)
    except OSError:
        for name in reversed(written):
            if name in existing:
                shutil.copy2(backup / name, root / name)
            else:
                (root / name).unlink(missing_ok=True)
        raise
    return backup


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Comprobar sin modificar archivos")
    args = parser.parse_args()
    if sys.platform != "win32":
        raise SystemExit("Este instalador es para Windows.")
    root = Path(git(Path.cwd(), "rev-parse", "--show-toplevel").decode().strip())
    try:
        git(root, "rev-parse", "--verify", f"{TARGET}:scripts/install_pr24_windows.py")
        planned = changes(root)
    except (RuntimeError, ValueError) as error:
        raise SystemExit(str(error) + "\nSi aparece un conflicto, enviame la lista para adaptar el instalador.") from error
    print(f"Comprobación correcta: {len(planned)} archivo(s) por instalar. No se tocó el catálogo ni runtime.")
    if args.check or not planned:
        return
    backup = install(root, planned)
    print(f"Instalación terminada. Respaldo: {backup}")
    print("Cerrá LexIA completamente y volvé a abrirla. No hace falta reconstruir el .exe.")


if __name__ == "__main__":
    main()
