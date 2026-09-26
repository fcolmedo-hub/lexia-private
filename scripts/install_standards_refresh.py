#!/usr/bin/env python3
"""Install the shared Standards and UI refresh after a Git fetch, preserving local work."""
from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path
import shutil
import subprocess
import tarfile
import tempfile


BASE = "29b1647f42e64bcfcd766864d01b043ad48074b9"
PREVIOUS = (
    "b1c98570dee6c805c4e74abecfd5754f8769eee0",
    "565a5ed0880313c2a2efc911125da19c0147c7a1",
    "a9197b6a8974b890ba7e16cd96fd03ef6415e8d7",
)
FILES = (
    "app/ui2/assets/shared_ui_consistency.css",
    "app/ui2/assets/standards_nav_fix.js",
    "app/ui2/assets/windows_maintenance_duplicates.js",
    "prompt/standards_extraction_v5.txt",
    "services/standards_pipeline.py",
    "standards/ENGINE.md",
    "tools/actualizar_diccionario_estandares.py",
    "tools/aplicar_relaciones_estandares.py",
    "tools/exportar_estandares_piloto.py",
    "tools/importar_estandares_sqlite.py",
    "tools/preparar_canonicalizacion_estandares.py",
    "tools/preparar_estandares_v2.py",
    "tools/preparar_estandares_v5.py",
    "tools/preseleccionar_fallos_estandares.py",
    "tools/procesar_canonicalizacion_batch.py",
    "tools/procesar_estandares_batch_v5.py",
    "tools/validar_estandares_v2.py",
    "tools/validar_estandares_v5.py",
)


def git(*args: str, cwd: Path | None = None, data: bytes | None = None):
    return subprocess.run(
        ["git", *args], cwd=cwd, input=data,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )


def installed(root: Path) -> bool:
    for name in FILES:
        file = root / name
        if not file.is_file():
            return False
        actual = git("hash-object", "--path", name, str(file), cwd=root)
        target = git("rev-parse", "--verify", f"FETCH_HEAD:{name}", cwd=root)
        if actual.returncode or target.returncode or actual.stdout.strip() != target.stdout.strip():
            return False
    return True


def matches_revision(root: Path, revision: str) -> bool:
    if git("cat-file", "-e", f"{revision}^{{commit}}", cwd=root).returncode:
        return False
    changed = git("diff", "--name-only", BASE, revision, "--", *FILES, cwd=root)
    if changed.returncode or not changed.stdout.strip():
        return False
    for name in changed.stdout.decode().splitlines():
        file = root / name
        if not file.is_file():
            return False
        actual = git("hash-object", "--path", name, str(file), cwd=root)
        expected = git("rev-parse", "--verify", f"{revision}:{name}", cwd=root)
        if actual.returncode or expected.returncode or actual.stdout.strip() != expected.stdout.strip():
            return False
    return True


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Sólo comprobar; no modificar archivos")
    args = parser.parse_args(argv)
    root_result = git("rev-parse", "--show-toplevel")
    if root_result.returncode:
        raise SystemExit("Ejecutá este instalador dentro del repositorio LexIA.")
    root = Path(root_result.stdout.decode().strip())
    if git("merge-base", "--is-ancestor", BASE, "FETCH_HEAD", cwd=root).returncode:
        raise SystemExit("Primero ejecutá: git fetch origin fix/standards-ui-batch-refresh")
    if installed(root):
        print("Actualización ya instalada. No se modificó ningún archivo.")
        return
    patch_base = next((revision for revision in PREVIOUS if matches_revision(root, revision)), BASE)
    patch = git("diff", "--binary", patch_base, "FETCH_HEAD", "--", *FILES, cwd=root)
    if patch.returncode or not patch.stdout:
        raise SystemExit("No se pudo leer la actualización desde Git.")

    with tempfile.TemporaryDirectory(prefix="lexia-standards-preflight-") as temporary:
        simulation = Path(temporary)
        for name in FILES:
            source = root / name
            if source.is_file():
                target = simulation / name
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, target)
        preflight = git("apply", "--check", "-", cwd=simulation, data=patch.stdout)
        if preflight.returncode:
            detail = preflight.stderr.decode(errors="replace").strip()
            raise SystemExit(
                "Hay cambios locales incompatibles; no se modificó ningún archivo.\n"
                + detail + "\nEnviame este error para adaptar la actualización."
            )
    if args.check:
        print("Comprobación correcta. No se modificó ningún archivo.")
        return

    desktop = Path.home() / "Desktop"
    backup_parent = desktop if desktop.is_dir() else Path.home()
    backup = backup_parent / ("lexia-estandares-" + datetime.now().strftime("%Y%m%d-%H%M%S-%f"))
    backup.mkdir()
    with tarfile.open(backup / "archivos-anteriores.tar.gz", "w:gz") as archive:
        for name in FILES:
            if (root / name).is_file():
                archive.add(root / name, arcname=name)
    result = git("apply", "-", cwd=root, data=patch.stdout)
    if result.returncode:
        raise SystemExit("No se completó la instalación. Respaldo: " + str(backup) + "\n" + result.stderr.decode(errors="replace"))
    print("Interfaz y batch V5 instalados. Respaldo: " + str(backup))
    print("Cerrá LexIA por completo y volvé a abrirla. No hace falta reconstruir la aplicación.")


if __name__ == "__main__":
    main()
