#!/usr/bin/env python3
"""Instala límite ampliado y aviso previo al envío en macOS, preservando cambios locales."""

import argparse
from datetime import datetime
import os
from pathlib import Path
import shutil
import stat
import subprocess
import tempfile


BASE = "d97696724af0a61af3dbaa3a523ba7ec44820e08"
FILES = (
    "config/settings.py",
    "ai/knowledge_context_builder.py",
    "services/ui2_delete_bridge.py",
    "app/ui2/index.html",
)
MARKERS = {
    "config/settings.py": "context_builder_study_max_chars_per_document: int = 200000",
    "ai/knowledge_context_builder.py": '"source_lengths": source_lengths',
    "services/ui2_delete_bridge.py": '"phase": "awaiting_confirmation"',
    "app/ui2/index.html": "Enviar análisis parcial",
}


def git(*args):
    result = subprocess.run(["git", *args], capture_output=True)
    if result.returncode:
        raise RuntimeError(result.stderr.decode("utf-8", "replace").strip())
    return result.stdout


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
            base = git("show", f"{BASE}:{relative}")
            target = git("show", f"{source_sha}:{relative}")
            if MARKERS[relative].encode("utf-8") not in target:
                conflicts.append(f"{relative}: la revisión descargada no contiene el cambio esperado")
                continue
            if old == target:
                continue
            local_path = folder / f"{number}-local"
            base_path = folder / f"{number}-base"
            target_path = folder / f"{number}-target"
            for output, data in ((local_path, old), (base_path, base), (target_path, target)):
                output.write_bytes(data)
            result = subprocess.run(
                ["git", "merge-file", "-p", str(local_path), str(base_path), str(target_path)],
                capture_output=True,
            )
            if result.returncode or b"\x00" in result.stdout:
                conflicts.append(f"{relative}: los cambios locales se cruzan con esta actualización")
                continue
            if result.stdout != old:
                changes.append((relative, path, old, result.stdout))

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
