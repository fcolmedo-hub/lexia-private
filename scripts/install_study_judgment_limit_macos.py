#!/usr/bin/env python3
"""Amplía el contexto de Estudiar archivo sin reemplazar cambios locales."""

import argparse
from datetime import datetime
import os
from pathlib import Path
import shutil
import stat
import subprocess
import tempfile


CHANGES = {
    "config/settings.py": (
        "    context_builder_upload_max_chars: int = 95000\n"
        "    context_builder_exports_path: Path = _EXPORTS_PATH / \"context_packages\"\n",
        "    context_builder_upload_max_chars: int = 95000\n"
        "    # Estudiar archivos dispone de un presupuesto propio: ampliar un fallo no\n"
        "    # debe multiplicar el tamaño de las investigaciones y sus fuentes.\n"
        "    context_builder_study_max_total_chars: int = 220000\n"
        "    context_builder_study_max_chars_per_document: int = 200000\n"
        "    context_builder_exports_path: Path = _EXPORTS_PATH / \"context_packages\"\n",
    ),
    "ai/knowledge_context_builder.py": (
        "        max_total = int(\n"
        "            SETTINGS.context_builder_max_total_chars\n"
        "        )\n"
        "        per_document_limit = int(\n"
        "            SETTINGS.context_builder_upload_max_chars\n"
        "        )\n",
        "        max_total = int(\n"
        "            SETTINGS.context_builder_study_max_total_chars\n"
        "        )\n"
        "        per_document_limit = int(\n"
        "            SETTINGS.context_builder_study_max_chars_per_document\n"
        "        )\n",
    ),
}


def git(*args):
    result = subprocess.run(["git", *args], capture_output=True)
    if result.returncode:
        raise RuntimeError(result.stderr.decode("utf-8", "replace").strip())
    return result.stdout


def normal(raw):
    return raw.decode("utf-8-sig").replace("\r\n", "\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--source", default="FETCH_HEAD")
    args = parser.parse_args()
    root = Path(git("rev-parse", "--show-toplevel").decode().strip()).resolve()

    updates = []
    errors = []
    for relative, (before, after) in CHANGES.items():
        path = root
        for component in Path(relative).parts:
            path = path / component
            if path.is_symlink():
                errors.append(f"{relative}: la ruta contiene un enlace simbólico")
                break
        if not path.is_file():
            errors.append(f"{relative}: falta el archivo")
            continue
        try:
            expected = normal(git("show", f"{args.source}:{relative}"))
        except RuntimeError as error:
            errors.append(f"{relative}: la revisión descargada no contiene el archivo ({error})")
            continue
        if expected.count(after) != 1 or before in expected:
            errors.append(f"{relative}: la revisión descargada no coincide con este instalador")
            continue
        raw = path.read_bytes()
        current = normal(raw)
        if current.count(after) == 1 and before not in current:
            continue
        if current.count(before) != 1 or after in current:
            errors.append(f"{relative}: los cambios locales requieren adaptar la actualización")
            continue
        next_text = current.replace(before, after, 1)
        newline = "\r\n" if raw.count(b"\r\n") > raw.count(b"\n") - raw.count(b"\r\n") else "\n"
        payload = (("\ufeff" if raw.startswith(b"\xef\xbb\xbf") else "") + next_text.replace("\n", newline)).encode("utf-8")
        updates.append((relative, path, raw, payload))

    if errors:
        print("Conflictos detectados:")
        for error in errors:
            print("- " + error)
        raise ValueError("No se modificó LexIA.")
    if not updates:
        print("El límite ampliado del estudio ya está instalado.")
        return
    print(f"Comprobación correcta: {len(updates)} archivo(s) por actualizar. Catálogo y runtime se conservan.")
    if args.check:
        return

    backup_root = Path.home() / "Desktop"
    if not backup_root.is_dir():
        backup_root = Path.home()
    backup = backup_root / ("lexia-estudio-respaldo-" + datetime.now().strftime("%Y%m%d-%H%M%S-%f"))
    backup.mkdir()
    for relative, path, _raw, _payload in updates:
        saved = backup / relative
        saved.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, saved)

    installed = []
    try:
        for _relative, path, raw, payload in updates:
            if path.read_bytes() != raw:
                raise ValueError("Un archivo cambió durante la instalación; se restaurará el respaldo.")
            temporary = None
            try:
                with tempfile.NamedTemporaryFile(dir=path.parent, prefix=".lexia-estudio-", delete=False) as out:
                    temporary = Path(out.name)
                    out.write(payload)
                    out.flush()
                    os.fsync(out.fileno())
                temporary.chmod(stat.S_IMODE(path.stat().st_mode))
                os.replace(temporary, path)
                installed.append((path, raw))
            finally:
                if temporary is not None:
                    temporary.unlink(missing_ok=True)
    except Exception:
        for path, raw in reversed(installed):
            path.write_bytes(raw)
        raise
    print(f"Instalación terminada. Respaldo: {backup}")
    print("Cerrá LexIA completamente y volvé a abrirla. No hace falta reconstruir la aplicación.")


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, RuntimeError) as error:
        raise SystemExit(str(error)) from error
