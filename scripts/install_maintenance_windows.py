#!/usr/bin/env python3
"""Safely install the incremental Maintenance UI updates on a Windows checkout."""
import argparse
from datetime import datetime
from pathlib import Path
import shutil
import subprocess
import tarfile
import tempfile


TARGET = "63b9db40c4515315d031f0517212235b1c9e26cf"
PHASES = (
    (
        "OCR por archivo y Duplicados",
        "400a1013e493438d6c898a9a55bb6861e97fd691",
        "0c79d67ad058cc61e0ac38d3984d4f1e29ff379c",
        (
            "app/ui2/assets/maintenance.css",
            "app/ui2/assets/maintenance.js",
            "app/ui2/assets/windows_maintenance_duplicates.js",
            "services/ocr_queue_service.py",
            "services/ui2_delete_bridge.py",
            "storage/ocr_queue_repository.py",
        ),
    ),
    (
        "AutoSync y navegación de Mantenimiento",
        "0c79d67ad058cc61e0ac38d3984d4f1e29ff379c",
        "f91298384fd2ae9689d81b23b1f58f64d721c20b",
        (
            "app/ui2/assets/maintenance.css",
            "app/ui2/assets/maintenance.js",
            "app/ui2/assets/windows_maintenance_status_detail.js",
            "app/ui2/navigator_3_3_4a.js",
            "core/document_detector.py",
            "services/autosync_service.py",
            "services/library_snapshot_service.py",
        ),
    ),
    (
        "Listado de Duplicados con formato OCR",
        "f91298384fd2ae9689d81b23b1f58f64d721c20b",
        TARGET,
        ("app/ui2/assets/windows_maintenance_duplicates.js",),
    ),
)


def git(*args, cwd=None, data=None):
    return subprocess.run(
        ["git", *args], cwd=cwd, input=data, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )


def installed(path, paths, revisions, repository):
    for name in paths:
        actual = git("hash-object", "--path", name, str(path / name), cwd=repository)
        if actual.returncode:
            return False
        valid = set()
        for revision in revisions:
            blob = git("rev-parse", "--verify", f"{revision}:{name}", cwd=repository)
            if blob.returncode == 0:
                valid.add(blob.stdout.strip())
        if actual.stdout.strip() not in valid:
            return False
    return True


def phase_installed(path, position, repository=None):
    _, _, target, files = PHASES[position]
    # Earlier changes to shared UI files can be superseded by later phases.
    # Every affected file must match a known published version; local changes
    # must still pass the patch preflight, not be declared installed.
    later = [target] + [phase[2] for phase in PHASES[position + 1:]]
    return installed(path, files, later, repository or path)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Only check compatibility; change nothing")
    args = parser.parse_args(argv)

    root = git("rev-parse", "--show-toplevel")
    if root.returncode:
        raise SystemExit("Abrí la terminal dentro de D:\\LexIA_2.3_DEV.")
    project = Path(root.stdout.decode().strip())
    remote = git("rev-parse", "--verify", "FETCH_HEAD", cwd=project)
    ancestor = git("merge-base", "--is-ancestor", TARGET, "FETCH_HEAD", cwd=project)
    if remote.returncode or ancestor.returncode:
        raise SystemExit("Primero ejecutá: git fetch origin fix/maintenance-duplicates-layout")
    files = sorted({name for _, _, _, names in PHASES for name in names})
    patches = []
    for label, before, after, names in PHASES:
        result = git("diff", "--binary", before, after, "--", *names, cwd=project)
        if result.returncode or not result.stdout:
            raise SystemExit("No se pudo leer la actualización desde Git. No se cambió ningún archivo.")
        patches.append(result.stdout)

    # Rehearse every required phase on a copy before writing to the checkout.
    with tempfile.TemporaryDirectory(prefix="lexia-maintenance-preflight-") as temporary:
        simulated = Path(temporary)
        for name in files:
            source = project / name
            if not source.is_file():
                raise SystemExit(f"Falta {name}. Actualizá la rama principal antes de instalar Mantenimiento.")
            target = simulated / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
        plan = []
        for position, (label, _, _, _) in enumerate(PHASES):
            if phase_installed(simulated, position, project):
                plan.append("ya instalada")
                continue
            check = git("apply", "--check", "-", cwd=simulated, data=patches[position])
            if check.returncode:
                detail = check.stderr.decode(errors="replace").strip()
                raise SystemExit(
                    f"No se puede aplicar «{label}». No se modificó tu instalación.\n{detail}\n"
                    "Actualizá la rama principal o enviame este mensaje para adaptar el instalador."
                )
            result = git("apply", "-", cwd=simulated, data=patches[position])
            if result.returncode:
                raise SystemExit("Falló la comprobación de la actualización. No se modificó tu instalación.")
            plan.append("pendiente")

    for phase, status in zip(PHASES, plan):
        print(f"{phase[0]}: {status}")
    if args.check or all(status == "ya instalada" for status in plan):
        print("Comprobación correcta. No se modificó ningún archivo.")
        return

    desktop = Path.home() / "Desktop"
    parent = desktop if desktop.is_dir() else Path.home()
    backup = parent / ("lexia-mantenimiento-windows-" + datetime.now().strftime("%Y%m%d-%H%M%S-%f"))
    backup.mkdir()
    with tarfile.open(backup / "archivos-anteriores.tar.gz", "w:gz") as archive:
        for name in files:
            archive.add(project / name, arcname=name)
    for position, status in enumerate(plan):
        if status == "ya instalada":
            continue
        result = git("apply", "-", cwd=project, data=patches[position])
        if result.returncode:
            raise SystemExit(
                "La instalación quedó incompleta. No reconstruyas todavía. Respaldo: "
                + str(backup) + "\n" + result.stderr.decode(errors="replace")
            )
    print("Mantenimiento actualizado. Respaldo: " + str(backup))
    print("Cerrá LexIA por completo y abrila nuevamente. No hace falta reconstruir el .exe.")


if __name__ == "__main__":
    main()
