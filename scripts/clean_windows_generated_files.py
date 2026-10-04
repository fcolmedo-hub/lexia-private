"""Clean only reviewed generated files; never remove operational backups."""
import argparse
import datetime
import hashlib
import json
import os
from pathlib import Path
import socket
import stat
import subprocess
import sys


def linked(path):
    value = path.lstat()
    return path.is_symlink() or bool(getattr(value, "st_file_attributes", 0) & 1024)


def files_under(folder):
    """Inventory without following links or Windows junctions."""
    if linked(folder):
        raise ValueError(f"Carpeta enlazada: {folder}")
    pending = [folder]
    files, directories, links = [], [], []
    while pending:
        current = pending.pop()
        directories.append(current)
        for child in current.iterdir():
            if linked(child):
                # Directory links need special Windows handling: leave them alone.
                if child.is_dir() or not child.is_symlink():
                    raise ValueError(f"Enlace de directorio: {child}")
                links.append(child)
            elif child.is_dir():
                pending.append(child)
            elif stat.S_ISREG(child.lstat().st_mode):
                files.append(child)
            else:
                raise ValueError(f"Tipo de archivo inesperado: {child}")
    return files, directories, links


def safe_parents(root, path):
    relative = path.relative_to(root)
    current = root
    for part in relative.parts:
        if current.exists() and linked(current):
            raise ValueError(f"Ruta enlazada: {current}")
        current = current / part


def digest(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def make_plan(root, protected=()):
    paths, directories = [], []
    notes = []
    # Check local operational source as well as the published code reviewed for
    # this cleanup. Experiments and benchmark scripts may refer to the test DB.
    markers = ("lexia_document_fts_test.sqlite3", "fastembed_cache.incompleta-20260903-200508")
    for name in ("app", "ai", "config", "core", "services", "search", "storage"):
        folder = root / name
        if not folder.exists():
            continue
        regular, _, _ = files_under(folder)
        for path in regular:
            if path.suffix.lower() in (".py", ".js", ".json", ".ps1", ".bat", ".cmd"):
                content = path.read_text(encoding="utf-8-sig", errors="replace").casefold()
                if any(marker.casefold() in content for marker in markers):
                    raise ValueError(f"El codigo local hace referencia a un candidato: {path}")
    runtime = root / "runtime"
    experiment = runtime / "experiments" / "lexia_document_fts_test.sqlite3"
    for suffix in ("", "-wal", "-shm", "-journal"):
        path = experiment.with_name(experiment.name + suffix)
        safe_parents(root, path)
        if path.exists():
            if linked(path) or not path.is_file():
                raise ValueError(f"Base experimental enlazada: {path}")
            paths.append(path)
    cache = runtime / "fastembed_cache"
    old = runtime / "fastembed_cache.incompleta-20260903-200508"
    safe_parents(root, old)
    safe_parents(root, cache)
    if old.exists():
        if not cache.is_dir() or linked(cache):
            notes.append("Se conserva la cache incompleta: no se encontro la cache activa normal.")
        else:
            # Confirm the observed model is present, identical, and physically
            # inside the active cache, without loading or downloading a model.
            model = Path("models--qdrant--paraphrase-multilingual-MiniLM-L12-v2-onnx-Q") / "blobs" / "634d0f66c29dc934c8fa72b8a4fe91dd4d420a22f1d82a241058d4316e659a99"
            active_blob, old_blob = cache / model, old / model
            safe_parents(root, active_blob)
            safe_parents(root, old_blob)
            valid = (active_blob.is_file() and old_blob.is_file()
                     and not linked(active_blob) and not linked(old_blob)
                     and active_blob.stat().st_size > 0
                     and digest(active_blob) == digest(old_blob))
            if not valid:
                notes.append("Se conserva la cache incompleta: no se verifico el modelo activo duplicado.")
            else:
                # An active snapshot must never refer to the quarantine.
                for folder, children, names in os.walk(cache, followlinks=False):
                    for name in children + names:
                        if (Path(folder) / name).resolve().is_relative_to(old.resolve()):
                            raise ValueError("La cache activa depende de la cache incompleta.")
                regular, folders, links = files_under(old)
                paths.extend(regular + links)
                directories.extend(folders)
    preview = runtime / "preview_cache" / "office_pdf"
    safe_parents(root, preview)
    if preview.exists():
        if linked(preview):
            raise ValueError(f"Cache de vistas previas enlazada: {preview}")
        for path in preview.iterdir():
            # Only the exact generated PDF naming convention, not imported files
            # or unfinished LibreOffice work directories.
            if (path.suffix == ".pdf" and len(path.stem) == 64
                    and all(c in "0123456789abcdef" for c in path.stem)
                    and not linked(path) and path.is_file()):
                paths.append(path)
    for candidate in paths + directories:
        for keep in protected:
            keep = Path(keep).resolve()
            if candidate.resolve() == keep or keep.is_relative_to(candidate.resolve()) or candidate.resolve().is_relative_to(keep):
                raise ValueError(f"La configuracion usa un candidato a limpiar: {candidate}")
    git = subprocess.run(["git", "ls-files", "-z"], cwd=root, capture_output=True, check=True)
    tracked = {root / Path(os.fsdecode(p)) for p in git.stdout.split(b"\0") if p}
    if any(path in tracked for path in paths):
        raise ValueError("Hay archivos versionados entre los candidatos; no se borraron.")
    records = []
    for path in sorted(set(paths)):
        value = path.lstat()
        records.append({"path": str(path), "bytes": value.st_size,
                        "mtime_ns": value.st_mtime_ns, "mode": value.st_mode,
                        "inode": value.st_ino})
    return records, sorted(directories, key=lambda p: len(p.parts), reverse=True), notes


def check_stopped(root):
    for port in (8512, 8513, 8515, 8153):
        with socket.socket() as connection:
            connection.settimeout(0.3)
            if connection.connect_ex(("127.0.0.1", port)) == 0:
                raise ValueError(f"Cerra LexIA: el puerto {port} sigue activo.")
    command = "Get-CimInstance Win32_Process | Select-Object ProcessId,Name,ExecutablePath,CommandLine | ConvertTo-Json -Compress"
    result = subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", command], capture_output=True, text=True, check=True)
    processes = json.loads(result.stdout or "[]")
    if isinstance(processes, dict):
        processes = [processes]
    for item in processes:
        name = str(item.get("Name") or "").lower()
        if item["ProcessId"] != os.getpid() and ("python" in name or "lexia" in name or "soffice" in name):
            detail = str(item.get("ExecutablePath") or "") + " " + str(item.get("CommandLine") or "")
            if str(root).casefold() in detail.casefold():
                raise ValueError(f"Cerra el proceso de LexIA {item['ProcessId']} ({name}) antes de limpiar.")


def apply(root, records, directories, log):
    total = 0
    with log.open("x", encoding="utf-8") as stream:
        for record in records:
            path = Path(record["path"])
            safe_parents(root, path)
            value = path.lstat()
            actual = (value.st_size, value.st_mtime_ns, value.st_mode, value.st_ino)
            expected = tuple(record[k] for k in ("bytes", "mtime_ns", "mode", "inode"))
            if actual != expected:
                raise ValueError(f"El archivo cambio durante la comprobacion: {path}")
            stream.write(json.dumps({"event": "planned", **record}) + "\n")
            stream.flush()
            path.unlink()  # unlink never traverses file symlinks
            total += record["bytes"]
            stream.write(json.dumps({"event": "deleted", **record}) + "\n")
            stream.flush()
        for folder in directories:
            safe_parents(root, folder)
            if linked(folder):
                raise ValueError(f"La carpeta cambio a un enlace: {folder}")
            folder.rmdir()  # only empty directories; never recursive deletion
    return total


def backup_inventory(root):
    result = []
    candidates = list((root / "backups").glob("*"))
    candidates += list((root / "backups" / "milestones").glob("*"))
    candidates += list(root.glob("runtime_seed_*"))
    for folder in candidates:
        if not folder.is_dir() or linked(folder):
            continue
        total, count, databases = 0, 0, []
        for current, children, names in os.walk(folder, followlinks=False):
            children[:] = [name for name in children if not linked(Path(current) / name)]
            for name in names:
                path = Path(current) / name
                if linked(path):
                    continue
                count += 1
                total += path.stat().st_size
                if name.endswith(".sqlite3"):
                    databases.append(str(path.relative_to(folder)))
        result.append({"path": str(folder), "MB": round(total / 1024**2, 2),
                       "files": count, "databases": databases[:12]})
    return sorted(result, key=lambda item: item["MB"], reverse=True)[:12]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(r"D:\LexIA_2.3_DEV"))
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    if sys.platform != "win32":
        raise ValueError("Esta herramienta esta destinada a Windows.")
    root = args.root.absolute()
    if linked(root):
        raise ValueError("La raiz de LexIA es un enlace.")
    sys.path.insert(0, str(root))
    from config.settings import SETTINGS
    protected = [getattr(SETTINGS, name) for name in SETTINGS.__dataclass_fields__
                 if isinstance(getattr(SETTINGS, name), Path)
                 and name not in ("runtime_path", "logs_path", "backups_path", "exports_path")]
    check_stopped(root)
    records, directories, notes = make_plan(root, protected)
    print(json.dumps({"candidates": len(records), "MB": round(sum(r["bytes"] for r in records) / 1024**2, 2), "notes": notes}, indent=2))
    if args.apply:
        check_stopped(root)
        log_folder = root / "logs"
        safe_parents(root, log_folder / "cleanup.jsonl")
        log_folder.mkdir(exist_ok=True)
        log = log_folder / ("cleanup-" + datetime.datetime.now().strftime("%Y%m%d-%H%M%S-%f") + ".jsonl")
        count = apply(root, records, directories, log)
        print(f"Limpieza terminada. MB eliminados: {count / 1024**2:.2f}. Registro: {log}")
    print(json.dumps({"backups_preserved": backup_inventory(root)}, indent=2))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"Limpieza detenida: {exc}", file=sys.stderr)
        sys.exit(1)
