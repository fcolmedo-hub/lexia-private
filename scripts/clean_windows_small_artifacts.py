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

GUARD_REVISION = "73b4fd58c8a53e6bfed87ddf7880bdeb235f7de5"
MAX_BYTES = 1024 * 1024
SOURCE_DIRS = {"ai", "app", "assets", "config", "core", "legal", "models",
               "prompt", "scripts", "search", "services", "standards", "storage",
               "tests", "tools", "docs"}
TEST_CACHE_FILES = {".gitignore", "CACHEDIR.TAG", "README.md", "v/cache/nodeids",
                    "v/cache/lastfailed", "v/cache/stepwise"}
TEST_CACHE_TAG = b"Signature: 8a477f597d28d172789f06886806bc55d"


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


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(r"D:\LexIA_2.3_DEV"))
    parser.add_argument("--apply", action="store_true")
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
        details.update(cleanup_completed=True, files_removed=len(records),
                       MB_removed=round(removed / 1024**2, 2), deletion_log=str(log))
        report.write_text(json.dumps(details, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps({"cleanup_completed": True, "files_removed": len(records),
                          "MB_removed": details["MB_removed"], "report": str(report),
                          "review_preserved_total": len(review)}, ensure_ascii=False, indent=2))
    else:
        print("Solo revision: no se eliminaron archivos.")


if __name__ == "__main__":
    sys.dont_write_bytecode = True
    try:
        main()
    except Exception as exc:
        print(f"Limpieza detenida: {exc}", file=sys.stderr)
        sys.exit(1)
