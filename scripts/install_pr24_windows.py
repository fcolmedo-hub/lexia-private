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
PREVIOUS = "bb95aeed9b2fa4de224fe3a6f184e507f6975494"
PREVIOUS_FEATURE = "6b22864e45505b4bda1e106f23790c053d70243a"
PREVIOUS_INSTALLED = "5fabf7722253b74bd11a605cfde7621b52e37df6"
PREVIOUS_CURRENT = "57352ba850f047d59e0e9c84dc8af495fb80126e"
PREVIOUS_BATCH_UI = "effc5ed4d0e1c0cf67863593ce90df7fcdb72a77"
PREVIOUS_TREE_UI = "e2c3560898a441226715d7a8b51f2a9d13af92b3"
PREVIOUS_COLLAPSED_UI = "22b4b1249f73dbca92409043b00dae11b5bc5133"
PREVIOUS_COURT_LIST = "d120de171c13689e0c71a590dab83d9d490cc5d9"
PREVIOUS_FEDERAL_COURTS = "1d9fb0dc891c03e2e838d025c1c0d13c35edc3fa"
PREVIOUS_BATCH_NOTICE = "27f630fd3f497bb7f46151c33d62e153d6956c18"
TARGET = "FETCH_HEAD"


def git(root: Path, *args: str) -> bytes:
    result = subprocess.run(["git", *args], cwd=root, capture_output=True)
    if result.returncode:
        detail = (result.stderr or result.stdout).decode("utf-8", errors="replace").strip()
        raise RuntimeError(f"Falló git {' '.join(args)} (código {result.returncode}). {detail}".strip())
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
    # git merge-file returns the number of conflicts (capped at 127), so 2+
    # is also a merge conflict, not an unexplained process failure.
    if result.returncode < 0 or result.returncode >= 128:
        detail = result.stderr.decode("utf-8", errors="replace").strip()
        raise RuntimeError(f"Falló git merge-file (código {result.returncode}). {detail}")
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


def changes(root: Path, base: str = BASE, target: str = TARGET, previous: str = PREVIOUS, previous_feature: str = PREVIOUS_FEATURE, previous_installed: str = PREVIOUS_INSTALLED, previous_current: str = PREVIOUS_CURRENT, previous_batch_ui: str = PREVIOUS_BATCH_UI, previous_tree_ui: str = PREVIOUS_TREE_UI, previous_collapsed_ui: str = PREVIOUS_COLLAPSED_UI, previous_court_list: str = PREVIOUS_COURT_LIST, previous_federal_courts: str = PREVIOUS_FEDERAL_COURTS, previous_batch_notice: str = PREVIOUS_BATCH_NOTICE) -> dict[str, bytes]:
    # A shallow Windows checkout can have both objects but no complete parent
    # chain for merge-base. The three-way comparison only needs those objects.
    git(root, "rev-parse", "--verify", f"{base}^{{commit}}")
    git(root, "rev-parse", "--verify", f"{target}^{{commit}}")
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
        current = path.read_bytes() if path.is_file() else None
        if current is not None and decode(current)[0] == decode(target_content)[0]:
            continue
        if status == "A":
            if current is None and path.exists():
                conflicts.append(name + " (la ruta local no es un archivo)")
            elif current is None:
                planned[name] = target_content
            else:
                # Earlier installers may have added this path to the working
                # tree without a commit. Try their exact published versions.
                error = None
                for reference in (previous, previous_feature, previous_installed, previous_current, previous_batch_ui, previous_tree_ui, previous_collapsed_ui, previous_court_list, previous_federal_courts, previous_batch_notice):
                    try:
                        candidate = merge(current, git(root, "show", f"{reference}:{name}"), target_content)
                        break
                    except (RuntimeError, UnicodeError, ValueError) as caught:
                        error = caught
                else:
                    conflicts.append(name + " (" + str(error) + ")")
                    continue
                if candidate != current:
                    planned[name] = candidate
        else:
            if current is None:
                conflicts.append(name + " (falta el archivo local)")
                continue
            error = None
            for reference in (base, previous, previous_feature, previous_installed, previous_current, previous_batch_ui, previous_tree_ui, previous_collapsed_ui, previous_court_list, previous_federal_courts, previous_batch_notice):
                try:
                    candidate = merge(current, git(root, "show", f"{reference}:{name}"), target_content)
                    break
                except (RuntimeError, UnicodeError, ValueError) as caught:
                    error = caught
            else:
                conflicts.append(name + " (" + str(error) + ")")
                continue
            if candidate != current:
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
