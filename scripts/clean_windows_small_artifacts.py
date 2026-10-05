"""Review small local artifacts; remove only identifiable generated caches."""
import argparse
from collections import Counter
import datetime
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
import zipfile

GUARD_REVISION = "73b4fd58c8a53e6bfed87ddf7880bdeb235f7de5"
MAX_BYTES = 1024 * 1024
SOURCE_DIRS = {"ai", "app", "assets", "config", "core", "legal", "models",
               "prompt", "scripts", "search", "services", "standards", "storage",
               "tests", "tools", "docs"}
TEST_CACHE_FILES = {".gitignore", "CACHEDIR.TAG", "README.md", "v/cache/nodeids",
                    "v/cache/lastfailed", "v/cache/stepwise"}
TEST_CACHE_TAG = b"Signature: 8a477f597d28d172789f06886806bc55d"
REVIEWED_COPIES = {
    "storage/catalog.py.backup_vector_hash_20260813_143543": "storage/catalog.py",
    "storage/catalog.py.bak_logfix_batch2": "storage/catalog.py",
    "storage/catalog.py.bak_vector_mark_probe": "storage/catalog.py",
    "services/autosync_service.py.bak_startup_echo_catalog_fix": "services/autosync_service.py",
    "services/ocr_queue_service.py.backup_trust_index_20260813_144048": "services/ocr_queue_service.py",
    "services/standards_service.py.respaldo-20260929-232118-079922": "services/standards_service.py",
    "app/ui.py.backup_antes_odt_import": "app/ui.py",
    "app/ui.py.backup_odt_dragdrop": "app/ui.py",
    "app/ui2/backend.py.respaldo-20260929-233300-415530": "app/ui2/backend.py",
    "app/ui2/server.py.backup_parse_qs_20260814_095937": "app/ui2/server.py",
    "scripts/install_maintenance_progress.py": None,
    "scripts/install_maintenance_windows.py": None,
    "scripts/install_pr24_windows.py": None,
    "scripts/install_standards_refresh.py": None,
    "app/backup_ui_331b_20260816_165201/ui.py": "app/ui.py",
    "app/ui2/backup_ui2_331a_20260816_151234/index.html": "app/ui2/index.html",
}


def load_guard(root):
    source = subprocess.check_output(["git", "show", GUARD_REVISION +
                                     ":scripts/clean_windows_generated_files.py"], cwd=root)
    result = {"__name__": "lexia_small_cleanup_guard"}
    exec(compile(source.decode("utf-8"), "lexia_small_cleanup_guard.py", "exec"), result)
    return result


def protected_path(path, protected):
    # No resolve(): following a junction is never needed for the inventory.
    return any(path == keep or path.is_relative_to(keep) or keep.is_relative_to(path)
               for keep in protected)


def source_for_bytecode(path):
    if path.parent.name == "__pycache__":
        match = re.fullmatch(r"(.+)\.cpython-\d+(?:\.opt-\d+|-pytest-\d+(?:\.\d+)*)?\.pyc", path.name)
        return path.parent.parent / (match[1] + ".py") if match else None
    return path.with_suffix(".py") if path.suffix == ".pyc" else None


def cache_reason(path, guard):
    source = source_for_bytecode(path)
    if source is not None and source.is_file() and not guard["linked"](source):
        return "bytecode_python_con_fuente_presente"
    if source is not None and source.name.startswith("test_") and "tests" in source.parts:
        obsolete = source.with_name(source.name + ".obsolete")
        if obsolete.is_file() and not guard["linked"](obsolete):
            return "bytecode_prueba_obsoleta_con_fuente_conservada"
    if path.name == ".DS_Store":
        with path.open("rb") as stream:
            if stream.read(8) == b"\x00\x00\x00\x01Bud1":
                return "cache_de_Finder"
    if path.name.casefold() == "thumbs.db":
        with path.open("rb") as stream:
            if stream.read(8) == b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1":
                return "cache_de_miniaturas"
    for parent in path.parents:
        if parent.name == ".pytest_cache":
            relative = path.relative_to(parent).as_posix()
            tag = parent / "CACHEDIR.TAG"
            if relative in TEST_CACHE_FILES and tag.is_file() and not guard["linked"](tag):
                with tag.open("rb") as stream:
                    if stream.read(len(TEST_CACHE_TAG)) == TEST_CACHE_TAG:
                        return "cache_de_pytest"
            break
    return None


def review_reason(path):
    lower = path.name.casefold()
    if (lower.endswith((".tmp", ".bak", ".orig", ".rej", "~")) or
            any(marker in lower for marker in (".backup_", ".bak_", ".respaldo-"))):
        return "copia_o_temporal_local_sin_origen_verificado"
    if lower.startswith(("install_", "instalar_")) and path.suffix in (".py", ".ps1", ".cmd"):
        return "instalador_local_no_versionado"
    if lower in {".ds_store", "thumbs.db"}:
        return "archivo_auxiliar_con_formato_no_verificado"
    if path.suffix in (".pyc", ".pyo"):
        return "bytecode_sin_fuente_identificable"
    return None


def make_plan(root, guard, protected=()):
    tracked_result = subprocess.check_output(["git", "ls-files", "-z"], cwd=root)
    tracked = {root / os.fsdecode(name) for name in tracked_result.split(b"\0") if name}
    protected = tuple(Path(path).absolute() for path in protected)
    records, review, skipped, cache_dirs = [], [], [], set()
    pending = [root]
    while pending:
        folder = pending.pop()
        for path in sorted(folder.iterdir()):
            relative = path.relative_to(root).as_posix()
            if guard["linked"](path):
                skipped.append({"path": relative, "reason": "enlace_conservado"})
                continue
            if protected_path(path, protected):
                skipped.append({"path": relative, "reason": "ruta_configurada_conservada"})
                continue
            value = path.lstat()
            if stat.S_ISDIR(value.st_mode):
                # Runtime, library, backups, installed app, builds, venv and Git
                # are not traversed. Unrecognized top-level folders are retained.
                if folder == root and path.name not in SOURCE_DIRS | {"__pycache__", ".pytest_cache"}:
                    skipped.append({"path": relative, "reason": "carpeta_fuera_del_alcance"})
                elif (path.name.casefold().startswith(("backup_", "backups", "respaldo")) or
                      path.name in {".venv", ".git", "node_modules"}):
                    skipped.append({"path": relative, "reason": "carpeta_conservada"})
                else:
                    pending.append(path)
                    if path.name in {"__pycache__", ".pytest_cache"} or ".pytest_cache" in path.parts:
                        cache_dirs.add(path)
                continue
            if not stat.S_ISREG(value.st_mode) or path in tracked or value.st_size > MAX_BYTES:
                continue
            reason = cache_reason(path, guard)
            if reason:
                records.append({"path": str(path), "relative": relative, "reason": reason,
                                "bytes": value.st_size, "mtime_ns": value.st_mtime_ns,
                                "mode": value.st_mode, "inode": value.st_ino})
            else:
                reason = review_reason(path)
                if reason:
                    review.append({"path": relative, "bytes": value.st_size, "reason": reason})
    return records, cache_dirs, review, skipped


def clean(root, records, cache_dirs, guard, log):
    # Reuse the audited per-file unlink and change checks. Empty cache folders
    # are optional: an unknown file inside any cache directory stays in place.
    removed = guard["apply"](root, records, [], log)
    for folder in sorted(cache_dirs, key=lambda path: len(path.parts), reverse=True):
        guard["safe_parents"](root, folder)
        if folder.exists() and not guard["linked"](folder) and not any(folder.iterdir()):
            folder.rmdir()
    return removed


def backup_folder_inventory(root, skipped, guard):
    result = []
    for item in skipped:
        folder = root / item["path"]
        if item["reason"] != "carpeta_conservada" or not folder.name.casefold().startswith(("backup", "respaldo")):
            continue
        files, pending, links = [], [folder], 0
        while pending:
            current = pending.pop()
            guard["safe_parents"](root, current)
            if guard["linked"](current):
                links += 1
                continue
            for path in sorted(current.iterdir()):
                if guard["linked"](path):
                    links += 1
                elif path.is_dir():
                    pending.append(path)
                elif path.is_file():
                    files.append({"path": path.relative_to(root).as_posix(), "bytes": path.stat().st_size})
        result.append({"path": item["path"], "files_total": len(files),
                       "MB": round(sum(file["bytes"] for file in files) / 1024**2, 2),
                       "links_skipped": links, "files": files})
    return result


def consolidate_reviewed(root, review, folders, protected, guard, stamp):
    """Archive reviewed unused artifacts before removing loose copies."""
    print("Comprobando referencias a las copias locales...", flush=True)
    tracked = {root / os.fsdecode(name) for name in
               subprocess.check_output(["git", "ls-files", "-z"], cwd=root).split(b"\0") if name}
    names = {item["path"] for item in review if item["path"] in REVIEWED_COPIES}
    names.update(item["path"] for item in review
                 if item["reason"] == "bytecode_sin_fuente_identificable"
                 and (root / item["path"]).parent.name == "__pycache__"
                 and source_for_bytecode(root / item["path"]) is not None)
    for folder in folders:
        if folder["links_skipped"] == 0 and folder["files_total"] == 1:
            name = folder["files"][0]["path"]
            if name in REVIEWED_COPIES:
                names.add(name)
    candidates, kept = [], []
    for name in sorted(names):
        path = root / name
        guard["safe_parents"](root, path)
        active = REVIEWED_COPIES.get(name)
        if (path in tracked or protected_path(path, protected) or guard["linked"](path)
                or not path.is_file() or path.stat().st_size > 4 * MAX_BYTES):
            kept.append({"path": name, "reason": "archivo_protegido_o_fuera_del_alcance"})
        elif active and (not (root / active).is_file() or guard["linked"](root / active)):
            kept.append({"path": name, "reason": "falta_el_archivo_operativo_actual"})
        else:
            candidates.append(path)
    # Read local executable code/configuration, including local edits and launchers.
    # Exclude the artifacts being archived and cleanup/test fixtures themselves.
    texts = []
    allowed = {".py", ".js", ".json", ".html", ".ps1", ".bat", ".cmd", ".sh", ".command", ".toml", ".ini"}
    pending = [root]
    while pending:
        folder = pending.pop()
        for path in folder.iterdir():
            if guard["linked"](path) or protected_path(path, protected):
                continue
            if path.is_dir():
                if ((folder == root and path.name not in SOURCE_DIRS - {"tests", "docs"})
                        or path.name in {"__pycache__", ".venv", ".git", "node_modules"}
                        or path.name.casefold().startswith(("backup", "respaldo"))):
                    continue
                pending.append(path)
            elif (path.suffix.casefold() in allowed and path not in candidates
                  and path.name not in {"clean_windows_small_artifacts.py", "clean_windows_generated_files.py", "compact_windows_historical_backups.py"}):
                texts.append((path.relative_to(root).as_posix(), path.read_text(encoding="utf-8-sig", errors="replace").casefold()))
    records = []
    for path in candidates:
        name = path.relative_to(root).as_posix()
        markers = {name.casefold(), name.replace("/", "\\").casefold(), path.name.casefold()}
        if path.parent.name.startswith("backup"):
            markers = {path.parent.name.casefold()}
        references = [source for source, text in texts if any(marker in text for marker in markers)]
        if references:
            kept.append({"path": name, "reason": "referencia_en_codigo_local", "references": references})
            continue
        value = path.stat()
        records.append({"path": str(path), "relative": name, "bytes": value.st_size,
                        "mtime_ns": value.st_mtime_ns, "mode": value.st_mode,
                        "inode": value.st_ino, "sha256": guard["digest"](path),
                        "reason": "artefacto_local_conservado_en_zip"})
    if not records:
        return {"files_consolidated": 0, "preserved": kept}
    if sum(item["bytes"] for item in records) > 16 * MAX_BYTES:
        raise ValueError("Las copias locales superan 16 MB; se conserva todo para revisar el alcance.")
    archive = root / "backups" / ("local-artifacts-" + stamp + ".zip")
    guard["safe_parents"](root, archive)
    archive.parent.mkdir(exist_ok=True)
    print(f"Consolidando {len(records)} archivos en un ZIP...", flush=True)
    with zipfile.ZipFile(archive, "x", compression=zipfile.ZIP_DEFLATED) as package:
        for item in records:
            package.write(item["path"], item["relative"])
        package.writestr("__cleanup_manifest__.json", json.dumps(records, ensure_ascii=False, indent=2))
    with zipfile.ZipFile(archive) as package:
        if package.testzip() is not None:
            raise ValueError("El ZIP no supero la comprobacion CRC; no se retiraron las copias locales.")
        import hashlib
        for item in records:
            if hashlib.sha256(package.read(item["relative"])).hexdigest() != item["sha256"]:
                raise ValueError("El ZIP no conserva el contenido original; no se retiraron copias locales.")
    # Verify all files before the first unlink. The shared guard checks them again.
    for item in records:
        path = Path(item["path"])
        guard["safe_parents"](root, path)
        if guard["linked"](path) or guard["digest"](path) != item["sha256"]:
            raise ValueError(f"Una copia cambio durante el respaldo: {item['relative']}")
    guard["check_stopped"](root)
    log = root / "logs" / ("local-artifacts-" + stamp + ".jsonl")
    removed = guard["apply"](root, records, [], log)
    for path in sorted({Path(item["path"]).parent for item in records}, key=lambda p: len(p.parts), reverse=True):
        if (path.name == "__pycache__" or path.name.startswith("backup_")) and path.exists() and not guard["linked"](path) and not any(path.iterdir()):
            path.rmdir()
    return {"files_consolidated": len(records), "MB_net_recovered": round((removed - archive.stat().st_size) / 1024**2, 2),
            "archive": str(archive), "deletion_log": str(log), "preserved": kept}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(r"D:\LexIA_2.3_DEV"))
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--consolidate-reviewed", action="store_true")
    args = parser.parse_args()
    if sys.platform != "win32":
        raise ValueError("Esta herramienta esta destinada a Windows.")
    root = args.root.absolute()
    guard = load_guard(root)
    if guard["linked"](root):
        raise ValueError("La raiz de LexIA es un enlace.")
    guard["check_stopped"](root)
    # Import settings without producing new bytecode during the cleanup.
    sys.path.insert(0, str(root))
    from config.settings import SETTINGS
    protected = [getattr(SETTINGS, name) for name in SETTINGS.__dataclass_fields__
                 if isinstance(getattr(SETTINGS, name), Path)]
    records, cache_dirs, review, skipped = make_plan(root, guard, protected)
    folders = backup_folder_inventory(root, skipped, guard)
    groups = Counter(record["reason"] for record in records)
    bytecode_review = [item for item in review if item["reason"] == "bytecode_sin_fuente_identificable"]
    other_review = [item for item in review if item["reason"] != "bytecode_sin_fuente_identificable"]
    logs = root / "logs"
    guard["safe_parents"](root, logs / "small-cleanup.json")
    logs.mkdir(exist_ok=True)
    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    report = logs / ("small-cleanup-" + stamp + ".json")
    details = {"apply_requested": args.apply, "candidates": records,
               "review_preserved": review, "skipped": skipped,
               "backup_folders_preserved": folders, "cleanup_completed": False}
    with report.open("x", encoding="utf-8") as stream:
        json.dump(details, stream, ensure_ascii=False, indent=2)
    print(json.dumps({"candidates": len(records), "by_type": dict(groups),
                      "MB": round(sum(record["bytes"] for record in records) / 1024**2, 2),
                      "review_preserved": other_review[:80], "review_preserved_total": len(review),
                      "other_review_total": len(other_review),
                      "bytecode_preserved_total": len(bytecode_review),
                      "bytecode_preserved_examples": bytecode_review[:8],
                      "preserved_folders_for_review": [{**item, "files": item["files"][:80]} for item in folders],
                      "report": str(report)}, ensure_ascii=False, indent=2), flush=True)
    if args.apply:
        guard["check_stopped"](root)
        log = logs / ("small-cleanup-" + stamp + ".jsonl")
        removed = clean(root, records, cache_dirs, guard, log)
        consolidation = (consolidate_reviewed(root, review, folders, protected, guard, stamp)
                         if args.consolidate_reviewed else None)
        details.update(cleanup_completed=True, files_removed=len(records),
                       MB_removed=round(removed / 1024**2, 2), deletion_log=str(log),
                       consolidation=consolidation)
        report.write_text(json.dumps(details, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps({"cleanup_completed": True, "files_removed": len(records),
                          "MB_removed": details["MB_removed"], "report": str(report),
                          "review_preserved_total_before_consolidation": len(review),
                          "consolidation": consolidation}, ensure_ascii=False, indent=2))
    else:
        print("Solo revision: no se eliminaron archivos.")


if __name__ == "__main__":
    sys.dont_write_bytecode = True
    try:
        main()
    except Exception as exc:
        print(f"Limpieza detenida: {exc}", file=sys.stderr)
        sys.exit(1)
