"""Retire old catalogs only after verified current database and code backups."""
import argparse
from contextlib import closing
import copy
import datetime
import hashlib
import json
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import zipfile

GUARD_REVISION = "73b4fd58c8a53e6bfed87ddf7880bdeb235f7de5"
BASELINE = "backups/LexIA_3_4_Baseline_pre_estabilizacion_20260820_165736"
MILESTONE = "backups/milestones/lexia_stable_3_3_20260810_164419"
SEED = "runtime_seed_20260804_183155"
RETIRED = (
    "runtime/lexia_catalog.sqlite3",
    SEED + "/lexia_catalog.sqlite3",
    "runtime/experiments/lexia_document_fts_test.sqlite3",
)


def digest(path):
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def fingerprint(path):
    value = path.stat()
    return [value.st_size, value.st_mtime_ns]


def dropped(name, project_name="LexIA_2.3_DEV"):
    name = name.replace("\\", "/")
    if name.split("/", 1)[0].casefold() == project_name.casefold():
        name = name.split("/", 1)[1] if "/" in name else ""
    return any(name == base + suffix for base in RETIRED
               for suffix in ("", "-wal", "-shm", "-journal"))


def compact_archive(path, project_name="LexIA_2.3_DEV"):
    """Stream the ZIP; preserve every retained entry and its verified CRC."""
    previous = fingerprint(path)
    original_size = previous[0]
    with zipfile.ZipFile(path) as source:
        kept = [info for info in source.infolist() if not dropped(info.filename, project_name)]
        removed = [info.filename for info in source.infolist() if dropped(info.filename, project_name)]
        if not removed:
            return 0, []
        fd, temporary_name = tempfile.mkstemp(prefix=".lexia-compact-", suffix=".zip", dir=path.parent)
        os.close(fd)
        temporary = Path(temporary_name)
        try:
            with zipfile.ZipFile(temporary, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as target:
                target.comment = source.comment
                for info in kept:
                    copied = copy.copy(info)
                    copied.compress_type = zipfile.ZIP_DEFLATED
                    if info.is_dir():
                        target.writestr(copied, b"")
                    else:
                        with source.open(info) as incoming, target.open(copied, "w", force_zip64=True) as outgoing:
                            shutil.copyfileobj(incoming, outgoing, 1024 * 1024)
            with zipfile.ZipFile(temporary) as rebuilt:
                if rebuilt.testzip() is not None:
                    raise ValueError("El ZIP compacto no supero la comprobacion CRC.")
                old = [(info.filename, info.file_size, info.CRC) for info in kept]
                new = [(info.filename, info.file_size, info.CRC) for info in rebuilt.infolist()]
                if old != new:
                    raise ValueError("El ZIP compacto no conserva todas las entradas previstas.")
            if fingerprint(path) != previous:
                raise ValueError("El ZIP original cambio durante la comprobacion.")
        except BaseException:
            temporary.unlink(missing_ok=True)
            raise
    # Windows requires closing the original ZIP before replacing it.
    try:
        if fingerprint(path) != previous:
            raise ValueError("El ZIP original cambio antes de reemplazarlo.")
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)
    return original_size - path.stat().st_size, removed


def snapshot_database(source, target):
    if target.exists():
        raise ValueError(f"La copia ya existe: {target}")
    target.parent.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(source.resolve().as_uri() + "?mode=ro", uri=True)) as original:
        with closing(sqlite3.connect(target)) as copied:
            original.backup(copied)
            copied.commit()
            if copied.execute("PRAGMA quick_check").fetchall() != [("ok",)]:
                raise ValueError(f"La copia SQLite no supero quick_check: {source.name}")
            if source.name == "lexia_catalog.sqlite3":
                before = original.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
                after = copied.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
                if not before or before != after:
                    raise ValueError("La copia del catalogo no conserva el conteo de documentos.")
    return digest(target)


def source_files(root, guard):
    result = subprocess.run(["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"], cwd=root, capture_output=True, check=True)
    excluded = {"runtime", "data", "data_test", "knowledge", "backups", "_backups", "exports", "Rejected Documents", "qdrant", "qdrant_storage", ".venv", ".git", "logs"}
    paths = set()
    for raw in result.stdout.split(b"\0"):
        if not raw:
            continue
        relative = Path(os.fsdecode(raw))
        if relative.parts[0] in excluded or relative.parts[0].startswith((".build_lexia", ".lexia_windows_app", "runtime_seed_")):
            continue
        path = root / relative
        guard["safe_parents"](root, path)
        if path.exists():
            if guard["linked"](path) or not path.is_file():
                raise ValueError(f"Archivo de codigo enlazado: {path}")
            paths.add(path)
    for folder in (root / ".lexia_windows_app",):
        if folder.exists():
            regular, _, links = guard["files_under"](folder)
            if links:
                raise ValueError("La aplicacion instalada contiene enlaces; se conserva sin limpiar.")
            paths.update(regular)
    for path in (root / ".env", root / "config/lexia.local.json", root / "config/library_tree.json"):
        if path.exists():
            guard["safe_parents"](root, path)
            if guard["linked"](path):
                raise ValueError(f"Configuracion enlazada: {path}")
            paths.add(path)
    # Operational settings and the library snapshot are small enough to retain;
    # the runs and original documents themselves remain untouched on disk.
    for path in (root / "runtime").glob("*.json"):
        guard["safe_parents"](root, path)
        if guard["linked"](path) or not path.is_file():
            raise ValueError(f"Estado operativo enlazado: {path}")
        paths.add(path)
    return sorted(paths)


def database_files(root, guard):
    found = []
    for current, directories, names in os.walk(root / "runtime", followlinks=False):
        directories[:] = [name for name in directories
                          if name not in ("experiments", "preview_cache")
                          and not name.startswith("fastembed_cache")
                          and not guard["linked"](Path(current) / name)]
        for name in names:
            if name.endswith(".sqlite3"):
                path = Path(current) / name
                guard["safe_parents"](root, path)
                if guard["linked"](path):
                    raise ValueError(f"Base actual enlazada: {path}")
                found.append(path)
    return sorted(found)


def recovery_backup(root, databases, code, guard):
    inputs = databases + code
    states = {str(path.relative_to(root)): fingerprint(path) for path in inputs}
    # Include pending WAL changes when deciding whether a prior backup is reusable.
    for source in databases:
        wal = source.with_name(source.name + "-wal")
        states[str(wal.relative_to(root))] = fingerprint(wal) if wal.exists() else None
    destination_root = root / "backups"
    guard["safe_parents"](root, destination_root / "cleanup_recovery_manifest.json")
    destination_root.mkdir(exist_ok=True)
    for previous in sorted(destination_root.glob("lexia-cleanup-current-*"), reverse=True):
        manifest_path = previous / "cleanup_recovery_manifest.json"
        if guard["linked"](previous) or not manifest_path.is_file() or guard["linked"](manifest_path):
            continue
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest.get("purpose") != "lexia-catalog-retirement-v1" or manifest.get("source_states") != states:
            continue
        expected = [str(path.relative_to(root)) for path in databases] + ["local_code_and_configuration.zip"]
        if sorted(manifest.get("sha256", {})) != sorted(expected):
            continue
        valid = True
        for name, value in manifest["sha256"].items():
            path = previous / name
            guard["safe_parents"](root, path)
            if not path.is_file() or guard["linked"](path) or digest(path) != value:
                valid = False
                break
        if valid:
            return previous, sum(path.stat().st_size for path in previous.rglob("*") if path.is_file()), False
    staging = Path(tempfile.mkdtemp(prefix=".lexia-cleanup-current-", dir=destination_root))
    committed = False
    try:
        hashes = {}
        for source in databases:
            print(f"Respaldando base: {source.relative_to(root)}", flush=True)
            relative = str(source.relative_to(root))
            hashes[relative] = snapshot_database(source, staging / relative)
        archive = staging / "local_code_and_configuration.zip"
        with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as backup:
            for path in code:
                backup.write(path, str(path.relative_to(root)))
            patch = subprocess.check_output(["git", "diff", "HEAD", "--binary"], cwd=root)
            backup.writestr("__cleanup_metadata__/git_worktree_changes.patch", patch)
        with zipfile.ZipFile(archive) as backup:
            if backup.testzip() is not None:
                raise ValueError("La copia del codigo no supero la comprobacion CRC.")
        hashes[archive.name] = digest(archive)
        for source in inputs:
            if fingerprint(source) != states[str(source.relative_to(root))]:
                raise ValueError(f"El archivo actual cambio durante el respaldo: {source}")
        for source in databases:
            wal = source.with_name(source.name + "-wal")
            if (fingerprint(wal) if wal.exists() else None) != states[str(wal.relative_to(root))]:
                raise ValueError(f"La base cambio durante el respaldo: {source.name}")
        manifest = {"purpose": "lexia-catalog-retirement-v1", "source_states": states, "sha256": hashes,
                    "note": "Copia verificada de bases SQLite y codigo/configuracion/aplicacion local. Biblioteca, archivos de ejecuciones IA y Qdrant no se retiran; sus originales se conservan. No es una copia integral del disco."}
        (staging / "cleanup_recovery_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        size = sum(path.stat().st_size for path in staging.rglob("*") if path.is_file())
        target = destination_root / ("lexia-cleanup-current-" + datetime.datetime.now().strftime("%Y%m%d-%H%M%S-%f"))
        staging.rename(target)
        committed = True
        return target, size, True
    finally:
        if not committed:
            shutil.rmtree(staging)


def load_guard(root):
    source = subprocess.check_output(["git", "show", GUARD_REVISION + ":scripts/clean_windows_generated_files.py"], cwd=root).decode("utf-8")
    guard = {"__name__": "lexia_cleanup_guard"}
    exec(compile(source, "lexia_cleanup_guard.py", "exec"), guard)
    return guard


def check_local_references(root, guard):
    markers = (Path(BASELINE).name, Path(MILESTONE).name, SEED)
    paths = []
    for name in ("app", "ai", "config", "core", "services", "search", "storage"):
        folder = root / name
        if folder.exists():
            paths.extend(guard["files_under"](folder)[0])
    paths.extend(root.glob("run_*.py"))
    for path in paths:
        if path.suffix.lower() in (".py", ".js", ".json", ".ps1", ".bat", ".cmd"):
            text = path.read_text(encoding="utf-8-sig", errors="replace").casefold()
            if any(marker.casefold() in text for marker in markers):
                raise ValueError(f"El codigo operativo local usa un respaldo a depurar: {path}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(r"D:\LexIA_2.3_DEV"))
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    if sys.platform != "win32":
        raise ValueError("Esta herramienta esta destinada a Windows.")
    root = args.root.absolute()
    guard = load_guard(root)
    guard["safe_parents"](root, root / "backups/catalog.sqlite3")
    if guard["linked"](root):
        raise ValueError("La raiz de LexIA esta enlazada.")
    sys.path.insert(0, str(root))
    from config.settings import SETTINGS
    if Path(SETTINGS.runtime_path).resolve() != (root / "runtime").resolve() or Path(SETTINGS.catalog_path).resolve() != (root / "runtime/lexia_catalog.sqlite3").resolve():
        raise ValueError("La configuracion utiliza otra ubicacion; no se retiraron copias.")
    guard["check_stopped"](root)
    check_local_references(root, guard)
    paths = []
    for relative in (BASELINE + "/runtime_sqlite/lexia_catalog.sqlite3", MILESTONE + "/databases/runtime/lexia_catalog.sqlite3", SEED + "/lexia_catalog.sqlite3"):
        for suffix in ("", "-wal", "-shm", "-journal"):
            path = root / (relative + suffix)
            guard["safe_parents"](root, path)
            if path.exists():
                if guard["linked"](path) or not path.is_file():
                    raise ValueError(f"Candidato enlazado: {path}")
                paths.append(path)
    archive = root / BASELINE / "codigo_y_configuracion.zip"
    guard["safe_parents"](root, archive)
    removed_members = []
    if archive.exists():
        if guard["linked"](archive):
            raise ValueError("El ZIP historico esta enlazado.")
        with zipfile.ZipFile(archive) as package:
            removed_members = [info.filename for info in package.infolist() if dropped(info.filename, root.name)]
    for candidate in paths + ([archive] if removed_members else []):
        for field in SETTINGS.__dataclass_fields__:
            value = getattr(SETTINGS, field)
            if isinstance(value, Path) and field not in ("runtime_path", "logs_path", "backups_path", "exports_path"):
                if candidate.resolve() == value.resolve() or candidate.resolve().is_relative_to(value.resolve()):
                    raise ValueError(f"La configuracion usa un candidato a limpiar: {candidate}")
    tracked = {root / Path(os.fsdecode(p)) for p in subprocess.check_output(["git", "ls-files", "-z"], cwd=root).split(b"\0") if p}
    if any(path in tracked for path in paths + [archive]):
        raise ValueError("Hay un candidato versionado; no se retiro.")
    qdrant_snapshots = list((root / MILESTONE / "qdrant").glob("*.snapshot"))
    snapshot_states = {str(path): fingerprint(path) for path in qdrant_snapshots}
    print(json.dumps({"old_catalogs": [str(p) for p in paths], "archive_entries_to_retire": removed_members}, indent=2), flush=True)
    if not args.apply or not (paths or removed_members):
        return
    states = {str(path): fingerprint(path) for path in paths}
    archive_state = fingerprint(archive) if archive.exists() else None
    databases = database_files(root, guard)
    if root / "runtime/lexia_catalog.sqlite3" not in databases:
        raise ValueError("No se encontro el catalogo actual para respaldar.")
    code = source_files(root, guard)
    code_bytes = sum(path.stat().st_size for path in code)
    if code_bytes > 512 * 1024**2:
        raise ValueError("El conjunto de codigo supera 512 MB; se conserva todo para revisar el alcance.")
    required = sum(path.stat().st_size for path in databases) + code_bytes + 128 * 1024**2
    if removed_members:
        with zipfile.ZipFile(archive) as package:
            required += 2 * sum(info.file_size for info in package.infolist() if not dropped(info.filename, root.name))
    if shutil.disk_usage(root).free < required:
        raise ValueError("No hay espacio para preparar y verificar las copias antes de depurar.")
    recovery, backup_bytes, created = recovery_backup(root, databases, code, guard)
    print(f"Respaldo actual verificado: {recovery}", flush=True)
    guard["check_stopped"](root)
    for path in paths:
        guard["safe_parents"](root, path)
        if guard["linked"](path) or fingerprint(path) != states[str(path)]:
            raise ValueError(f"Una copia antigua cambio durante la preparacion: {path}")
    guard["safe_parents"](root, archive)
    if archive.exists() and (guard["linked"](archive) or fingerprint(archive) != archive_state):
        raise ValueError("El ZIP antiguo cambio durante la preparacion.")
    # Mark each historical package as partial before modifying any of it.
    notice = {"catalog_replacement": str(recovery / "runtime/lexia_catalog.sqlite3"),
              "planned_catalog_retirement": [str(path) for path in paths], "status": "prepared",
              "note": "Respaldo historico parcialmente depurado. El catalogo antiguo se sustituye por la copia actual indicada. Se conservan documentos, codigo historico y snapshot Qdrant; ver manifest de recuperacion."}
    for relative in (BASELINE, MILESTONE, SEED):
        folder = root / relative
        if folder.exists():
            notice_path = folder / "CATALOGO_REEMPLAZADO_POR_COPIA_ACTUAL.json"
            guard["safe_parents"](root, notice_path)
            if notice_path.exists() and guard["linked"](notice_path):
                raise ValueError("La nota de recuperacion es un enlace.")
            notice_path.write_text(json.dumps(notice, indent=2), encoding="utf-8")
    reclaimed = 0
    with (recovery / "retirement_log.jsonl").open("a", encoding="utf-8") as log:
        if removed_members:
            guard["safe_parents"](root, archive)
            if guard["linked"](archive):
                raise ValueError("El ZIP antiguo cambio a un enlace.")
            log.write(json.dumps({"planned_zip_compaction": str(archive), "retired_entries": removed_members}) + "\n")
            log.flush()
            amount, _ = compact_archive(archive, root.name)
            reclaimed += amount
            log.write(json.dumps({"verified_zip_compaction": str(archive), "bytes_recovered": amount}) + "\n")
            log.flush()
            print(f"ZIP compacto verificado: {amount / 1024**2:.2f} MB menos.", flush=True)
        for path in paths:
            guard["safe_parents"](root, path)
            if guard["linked"](path) or fingerprint(path) != states[str(path)]:
                raise ValueError(f"Una copia cambio antes de retirarla: {path}")
            size = path.stat().st_size
            log.write(json.dumps({"planned_delete": str(path), "bytes": size}) + "\n")
            log.flush()
            path.unlink()
            reclaimed += size
            log.write(json.dumps({"deleted": str(path), "bytes": size}) + "\n")
            log.flush()
    notice["status"] = "completed"
    for relative in (BASELINE, MILESTONE, SEED):
        path = root / relative / "CATALOGO_REEMPLAZADO_POR_COPIA_ACTUAL.json"
        if path.parent.exists():
            guard["safe_parents"](root, path)
            if guard["linked"](path):
                raise ValueError("La nota de recuperacion cambio a un enlace.")
            path.write_text(json.dumps(notice, indent=2), encoding="utf-8")
    print(json.dumps({"cleanup_completed": True, "recovery_backup": str(recovery),
                      "MB_removed": round(reclaimed / 1024**2, 2),
                      "MB_new_backup": round(backup_bytes / 1024**2, 2) if created else 0,
                      "MB_net_recovered": round((reclaimed - (backup_bytes if created else 0)) / 1024**2, 2),
                      "qdrant_historical_snapshot_preserved": bool(qdrant_snapshots) and all(path.is_file() and fingerprint(path) == snapshot_states[str(path)] for path in qdrant_snapshots)}, indent=2))


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(f"Depuracion detenida: {error}", file=sys.stderr)
        sys.exit(1)
