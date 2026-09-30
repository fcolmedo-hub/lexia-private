"""Preselección revisable de fallos indexados para la extracción V5."""
from __future__ import annotations

import argparse
import json
import ntpath
import posixpath
import re
import sqlite3
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from config.settings import SETTINGS


def imported_documents(standards_db: Path) -> tuple[set[str], set[str]]:
    paths: set[str] = set()
    hashes: set[str] = set()
    if not standards_db.is_file():
        return paths, hashes
    with sqlite3.connect(f"file:{standards_db.resolve()}?mode=ro", uri=True) as connection:
        if not connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='documents'"
        ).fetchone():
            return paths, hashes
        columns = {row[1] for row in connection.execute("PRAGMA table_info(documents)")}
        fields = ["document_path"]
        if "source_key" in columns:
            fields.append("source_key")
        if "metadata_json" in columns:
            fields.append("metadata_json")
        for row in connection.execute(f"SELECT {', '.join(fields)} FROM documents"):
            if row[0]:
                paths.add(str(row[0]).casefold())
            if "source_key" in columns and str(row[fields.index("source_key")] or "").startswith("sha256:"):
                hashes.add(str(row[fields.index("source_key")])[7:].casefold())
    return paths, hashes


def pending_documents(runs_root: Path, *, exclude_run_id: str | None = None, submitted_only: bool = False) -> tuple[set[str], set[str]]:
    """Files prepared or submitted in another run but not yet imported."""
    paths: set[str] = set()
    hashes: set[str] = set()
    if not runs_root.is_dir():
        return paths, hashes
    for run in runs_root.iterdir():
        if not run.is_dir() or run.name == exclude_run_id:
            continue
        state_path = run / "state.json"
        source_path = run / "source" / "fallos.jsonl"
        if not state_path.is_file() or not source_path.is_file():
            continue
        state = json.loads(state_path.read_text(encoding="utf-8"))
        stage = str(state.get("stage") or "")
        if stage not in {"extraction_ready_to_submit", "extraction_submitted", "extraction_collected"}:
            continue
        sent = (run / "extraction_batch" / "batch_state.json").is_file() or stage == "extraction_submitted"
        if submitted_only and not sent:
            continue
        if not sent and stage != "extraction_ready_to_submit":
            continue
        for raw in source_path.read_text(encoding="utf-8").splitlines():
            if not raw.strip():
                continue
            doc = json.loads(raw)
            if doc.get("document_path"):
                paths.add(str(doc["document_path"]).casefold())
            if doc.get("content_hash"):
                hashes.add(str(doc["content_hash"]).casefold())
    return paths, hashes


def within_folder(path: str, folder: str | Path) -> bool:
    """Compare full directory boundaries, including Windows paths on any host."""
    source = str(path)
    selected = str(folder)
    windows = bool(re.match(r"^[A-Za-z]:[\\/]|^\\\\", selected))
    path_module = ntpath if windows else posixpath
    normalize = lambda value: path_module.normcase(path_module.normpath(value))
    root = normalize(selected)
    document = normalize(source)
    return document.startswith(root.rstrip("\\/") + path_module.sep)


def candidates(catalog: Path, standards_db: Path, contains: str, limit: int, *, folder: str | Path | None = None, runs_root: Path | None = None) -> list[str]:
    if not catalog.is_file():
        raise FileNotFoundError(f"No existe el catálogo: {catalog}")
    excluded, excluded_hashes = imported_documents(standards_db)
    if runs_root is not None:
        pending_paths, pending_hashes = pending_documents(runs_root)
        excluded.update(pending_paths)
        excluded_hashes.update(pending_hashes)

    result: list[str] = []
    with sqlite3.connect(f"file:{catalog.resolve()}?mode=ro", uri=True) as connection:
        connection.execute("PRAGMA query_only=ON")
        columns = {row[1] for row in connection.execute("PRAGMA table_info(documents)")}
        hash_column = "d.content_hash" if "content_hash" in columns else "''"
        rows = connection.execute(
            f"""SELECT d.path, {hash_column} FROM documents d
               WHERE d.category='Jurisprudencia' AND COALESCE(d.is_deleted,0)=0
                 AND instr(lower(d.path),lower(?))>0
               ORDER BY d.path COLLATE NOCASE""",
            (contains,),
        )
        selected_hashes: set[str] = set()
        for path, content_hash in rows:
            if folder is not None and not within_folder(str(path), folder):
                continue
            digest = str(content_hash or "").casefold()
            if (str(path).casefold() in excluded or
                    digest and (digest in excluded_hashes or digest in selected_hashes)):
                continue
            # The fragment table can be very large. Check only the few
            # candidate paths until the requested limit is reached.
            if not connection.execute(
                """SELECT 1 FROM fragments
                   WHERE document_path=? AND length(trim(text_content))>0 LIMIT 1""",
                (path,),
            ).fetchone():
                continue
            result.append(str(path))
            if digest:
                selected_hashes.add(digest)
            if len(result) >= limit:
                break
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalog", type=Path, default=Path(SETTINGS.catalog_path))
    parser.add_argument("--db", type=Path, default=Path(SETTINGS.runtime_path) / "standards" / "standards.sqlite3")
    parser.add_argument("--runs-root", type=Path, default=Path(SETTINGS.runtime_path) / "standards" / "runs")
    scope = parser.add_mutually_exclusive_group(required=True)
    scope.add_argument("--path-contains", help="Parte de la ruta que delimita el lote")
    scope.add_argument("--folder", type=Path, help="Carpeta exacta elegida; incluye sus subcarpetas")
    parser.add_argument("--limit", type=int, default=250)
    parser.add_argument("--output", type=Path, required=True, help="TXT de rutas para revisar antes de prepare")
    args = parser.parse_args()
    if not 1 <= args.limit <= 250:
        parser.error("Indicá un límite de 1 a 250 fallos.")
    if args.folder is not None and not args.folder.is_dir():
        parser.error(f"No existe la carpeta seleccionada: {args.folder}")
    if args.folder is None and not args.path_contains.strip():
        parser.error("Indicá una parte de la ruta.")
    if args.output.exists():
        parser.error(f"El archivo ya existe; no se sobrescribe: {args.output}")
    print(f"Revisando Jurisprudencia indexada en {args.catalog}…", flush=True)
    try:
        contains = args.path_contains.strip() if args.folder is None else args.folder.name
        paths = candidates(args.catalog, args.db, contains, args.limit, folder=args.folder, runs_root=args.runs_root)
    except (OSError, sqlite3.Error, ValueError) as error:
        parser.exit(1, f"No se pudo leer el catálogo: {error}\n")
    if not paths:
        parser.exit(1, "No hay fallos indexados nuevos en esa carpeta.\n")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text("\n".join(paths) + "\n", encoding="utf-8")
    print(f"{len(paths)} fallos preseleccionados en {args.output}. Revisá el TXT antes de preparar el lote; no se llamó a la API.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
