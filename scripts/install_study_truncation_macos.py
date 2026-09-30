#!/usr/bin/env python3
"""Instala límite ampliado y aviso previo en macOS y Windows, preservando cambios locales."""

import argparse
from datetime import datetime
import os
from pathlib import Path
import shutil
import stat
import subprocess
import tempfile


BASE = "d97696724af0a61af3dbaa3a523ba7ec44820e08"
PREVIOUS_PREVIEW = "142d2daf34f661c271f2c8402684c7b0df2444ff"
PREVIOUS_THEMATIC_PREVIEW = "7c95bf1787ce018bac8d09ec07220866aa9dcd85"
FILES = (
    "config/settings.py",
    "ai/knowledge_context_builder.py",
    "ai/thematic_document_study.py",
    "services/ui2_delete_bridge.py",
    "app/ui2/index.html",
)
MARKERS = {
    "config/settings.py": "context_builder_study_max_chars_per_document: int = 200000",
    "ai/knowledge_context_builder.py": '"source_lengths": source_lengths',
    "ai/thematic_document_study.py": "max_total = int(SETTINGS.context_builder_study_max_total_chars)",
    "services/ui2_delete_bridge.py": '"phase": "awaiting_confirmation"',
    "app/ui2/index.html": "Enviar análisis parcial",
}


def git(*args):
    result = subprocess.run(["git", *args], capture_output=True)
    if result.returncode:
        raise RuntimeError(result.stderr.decode("utf-8", "replace").strip())
    return result.stdout


def normalized(raw):
    return raw.decode("utf-8-sig").replace("\r\n", "\n").encode("utf-8")


def preserve_format(payload, original):
    newline = b"\r\n" if original.count(b"\r\n") > original.count(b"\n") / 2 else b"\n"
    prefix = b"\xef\xbb\xbf" if original.startswith(b"\xef\xbb\xbf") else b""
    return prefix + payload.replace(b"\n", newline)


def merge_study_html(local, base, target):
    # El cambio del PR solo afecta al controlador de Estudiar. Una combinación
    # de todo el HTML puede chocar con cambios locales contiguos de Windows.
    # Se sustituye exclusivamente un controlador reconocido, sin tocar el resto.
    start = b"  const study=replace('startStudy',"
    end = b"\n  replace('copyContext',"

    def bounds(data):
        if data.count(start) != 1 or data.count(end) != 1:
            raise ValueError("No se reconoce un controlador único de Estudiar.")
        first = data.index(start)
        last = data.index(end)
        if last <= first:
            raise ValueError("No se reconocen los límites del controlador de Estudiar.")
        return first, last

    local_start, local_end = bounds(local)
    base_start, base_end = bounds(base)
    target_start, target_end = bounds(target)
    before = base[base_start:base_end]
    after = target[target_start:target_end]
    # Este atajo no debe utilizarse si una revisión futura cambia otras zonas.
    if base[:base_start] + after + base[base_end:] != target:
        raise ValueError("La revisión modifica otras zonas del HTML.")
    current = local[local_start:local_end]
    if current == after:
        return local
    if current != before:
        raise ValueError("El controlador de Estudiar también tiene cambios locales.")
    return local[:local_start] + after + local[local_end:]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", default="FETCH_HEAD")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    root = Path(git("rev-parse", "--show-toplevel").decode().strip()).resolve()
    source_sha = git("rev-parse", "--verify", f"{args.source}^{{commit}}").decode().strip()
    # Una versión no descendiente de BASE no tiene el ancestro necesario para
    # preservar por combinación los cambios locales de una instalación anterior.
    git("merge-base", "--is-ancestor", BASE, source_sha)

    changes = []
    conflicts = []
    with tempfile.TemporaryDirectory(prefix="lexia-estudio-comprobar-") as tmp:
        folder = Path(tmp)
        for number, relative in enumerate(FILES):
            path = root
            for component in Path(relative).parts:
                path = path / component
                if path.is_symlink():
                    conflicts.append(f"{relative}: la ruta contiene un enlace simbólico")
                    break
            if not path.is_file():
                conflicts.append(f"{relative}: no existe en esta instalación")
                continue
            old = path.read_bytes()
            previous_markers = {
                "services/ui2_delete_bridge.py": b'"phase": "awaiting_confirmation"',
                "app/ui2/index.html": "Enviar análisis parcial".encode("utf-8"),
            }
            base_ref = (
                PREVIOUS_THEMATIC_PREVIEW
                if relative == "ai/thematic_document_study.py" and b'"study_selection": {' in old
                else PREVIOUS_PREVIEW
                if relative in previous_markers and previous_markers[relative] in old
                else BASE
            )
            base = git("show", f"{base_ref}:{relative}")
            target = git("show", f"{source_sha}:{relative}")
            if MARKERS[relative].encode("utf-8") not in target:
                conflicts.append(f"{relative}: la revisión descargada no contiene el cambio esperado")
                continue
            if old == target:
                continue
            local_path = folder / f"{number}-local"
            base_path = folder / f"{number}-base"
            target_path = folder / f"{number}-target"
            try:
                local_normal, base_normal, target_normal = map(normalized, (old, base, target))
            except UnicodeError:
                conflicts.append(f"{relative}: no tiene una codificación UTF-8 válida")
                continue
            for output, data in ((local_path, local_normal), (base_path, base_normal), (target_path, target_normal)):
                output.write_bytes(data)
            result = subprocess.run(
                ["git", "merge-file", "-p", str(local_path), str(base_path), str(target_path)],
                capture_output=True,
            )
            if result.returncode or b"\x00" in result.stdout:
                if relative != "app/ui2/index.html":
                    conflicts.append(f"{relative}: los cambios locales se cruzan con esta actualización")
                    continue
                try:
                    merged = merge_study_html(local_normal, base_normal, target_normal)
                except ValueError as error:
                    conflicts.append(f"{relative}: {error}")
                    continue
            else:
                merged = result.stdout
            payload = preserve_format(merged, old)
            if payload != old:
                changes.append((relative, path, old, payload))

    if conflicts:
        print("Conflictos detectados:")
        for conflict in conflicts:
            print("- " + conflict)
        raise ValueError("No se modificó LexIA.")
    if not changes:
        print("El aviso previo y el límite ampliado ya están instalados.")
        return
    print(f"Comprobación correcta: {len(changes)} archivo(s) por instalar. Catálogo y runtime se conservan.")
    if args.check:
        return

    desktop = Path.home() / "Desktop"
    backup_root = desktop if desktop.is_dir() else Path.home()
    backup = backup_root / ("lexia-estudio-aviso-respaldo-" + datetime.now().strftime("%Y%m%d-%H%M%S-%f"))
    backup.mkdir()
    for relative, path, _old, _new in changes:
        destination = backup / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, destination)

    installed = []
    try:
        for _relative, path, old, new in changes:
            if path.read_bytes() != old:
                raise ValueError("Un archivo cambió durante la instalación; se restaurarán los anteriores.")
            temporary = None
            try:
                with tempfile.NamedTemporaryFile(dir=path.parent, prefix=".lexia-estudio-", delete=False) as output:
                    temporary = Path(output.name)
                    output.write(new)
                    output.flush()
                    os.fsync(output.fileno())
                temporary.chmod(stat.S_IMODE(path.stat().st_mode))
                os.replace(temporary, path)
                installed.append((path, old))
            finally:
                if temporary is not None:
                    temporary.unlink(missing_ok=True)
    except Exception:
        for path, old in reversed(installed):
            path.write_bytes(old)
        raise
    print(f"Instalación terminada. Respaldo: {backup}")
    print("Cerrá LexIA completamente y volvé a abrirla. No hace falta reconstruir la aplicación.")


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, RuntimeError) as error:
        raise SystemExit(str(error)) from error
