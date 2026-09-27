"""Local, durable UI coordinator for standards extraction batches."""

from __future__ import annotations

import json
import math
import ntpath
import posixpath
import re
import sqlite3
import threading
import time
import uuid
from pathlib import Path
from typing import Any

from config.settings import SETTINGS
from services.standards_pipeline import StandardsPipeline
from tools.preseleccionar_fallos_estandares import candidates

CATALOG = Path(SETTINGS.catalog_path)
RUNS = Path(SETTINGS.runtime_path) / "standards" / "runs"
DB = Path(SETTINGS.runtime_path) / "standards" / "standards.sqlite3"
ROOT = Path(__file__).resolve().parents[1]
CHUNK = 250
MAX_SELECTION = 2500
_LOCK = threading.Lock()
_ACTIVE: set[str] = set()
_TREE_LOCK = threading.Lock()
_TREE_CACHE: dict[str, Any] = {}


def _path_parts(path: str) -> tuple[str, list[str], str]:
    """Return a Jurisprudencia root and each descendant folder on either OS."""
    module = ntpath if len(path) > 2 and path[1] == ":" or path.startswith("\\\\") else posixpath
    parent = module.dirname(module.normpath(path))
    parts = parent.replace("\\", "/").split("/")
    anchor = next((i for i, part in enumerate(parts) if part.casefold() == "jurisprudencia"), None)
    if anchor is None:
        return parent, [], module.sep
    root = module.normpath("/".join(parts[:anchor + 1]))
    return root, parts[anchor + 1:], module.sep


def _folder_index() -> dict[str, Any]:
    if not CATALOG.is_file():
        raise FileNotFoundError(f"No existe el catálogo: {CATALOG}")
    wal = Path(str(CATALOG) + "-wal")
    wal_stamp = (wal.stat().st_mtime_ns, wal.stat().st_size) if wal.exists() else None
    stamp = (str(CATALOG), CATALOG.stat().st_mtime_ns, CATALOG.stat().st_size, wal_stamp)
    with _TREE_LOCK:
        if _TREE_CACHE.get("stamp") == stamp:
            return _TREE_CACHE
        children: dict[str, set[str]] = {"": set()}
        counts: dict[str, int] = {}
        with sqlite3.connect(f"file:{CATALOG.resolve()}?mode=ro", uri=True) as connection:
            rows = connection.execute(
                "SELECT path FROM documents WHERE category='Jurisprudencia' AND COALESCE(is_deleted,0)=0"
            )
            for (path,) in rows:
                root, folders, separator = _path_parts(str(path))
                children[""].add(root)
                counts[root] = counts.get(root, 0) + 1
                parent = root
                for name in folders:
                    child = parent.rstrip("\\/") + separator + name
                    children.setdefault(parent, set()).add(child)
                    counts[child] = counts.get(child, 0) + 1
                    parent = child
        _TREE_CACHE.clear()
        _TREE_CACHE.update(stamp=stamp, children=children, counts=counts)
        return _TREE_CACHE


def folder_tree(parent: str = "") -> list[dict[str, Any]]:
    index = _folder_index()
    children = index["children"]
    if parent and parent not in index["counts"]:
        raise ValueError("La carpeta no figura en Jurisprudencia.")
    return [{"name": ntpath.basename(path.rstrip("\\/")) if "\\" in path else posixpath.basename(path.rstrip("/")),
             "path": path, "count": index["counts"][path], "has_children": bool(children.get(path))}
            for path in sorted(children.get(parent, ()), key=lambda item: item.casefold())]


def court_suggestions() -> dict[str, Any]:
    index = _folder_index()
    courts: dict[str, dict[str, str]] = {}
    for path in index["counts"]:
        _, parts, _ = _path_parts(path + ("\\_fallo.pdf" if "\\" in path else "/_fallo.pdf"))
        if not parts:
            continue
        segments = [part.strip() for part in parts if part.strip()]
        # A denomination on its own (for example "1º") is meaningful only
        # together with its Civil/Comercial and Primera Instancia ancestors.
        last = segments[-1]
        has_children = bool(index["children"].get(path))
        numbered = bool(re.fullmatch(r"\d{1,2}\s*[ªº°a]?", last, re.I)
                        and any(re.search(r"nominaci[oó]n|instancia|juzgad|c[aá]mara|sala", part, re.I)
                                for part in segments[:-1]))
        named = bool(re.search(r"juzgad|tribunal|c[aá]mara|corte|nominaci[oó]n|\bsala\b", last, re.I))
        administrative = bool(re.search(r"contencioso\s+administrativo", last, re.I))
        locality = bool(last.casefold() in {"rosario", "santa fe"}
                        and any(re.search(r"contencioso\s+administrativo|c[aá]mara federal", part, re.I)
                                for part in segments[:-1]))
        if not (numbered or named or administrative or locality):
            continue
        if has_children and re.fullmatch(r"nominaci[oó]n:?|\bsala\b", last, re.I):
            continue
        label = " › ".join(segments)
        if re.fullmatch(r"\d{1,2}\s*[ªº°a]?", last, re.I) and len(segments) > 1:
            prefix = segments[:-2] if re.fullmatch(r"nominaci[oó]n:?", segments[-2], re.I) else segments[:-1]
            label = " › ".join(prefix + ["Nominación " + last])
        subject = next((part for part in segments if re.search(r"civil|comercial|laboral|penal|familia|contencioso", part, re.I)), "")
        number = re.search(r"(\d{1,2})\s*[ªº°a]?", last) if re.search(r"nominaci[oó]n", last, re.I) or re.fullmatch(r"\d{1,2}\s*[ªº°a]?", last, re.I) else None
        suggested = ""
        if number and subject and any(re.search(r"primera instancia|juzgad", part, re.I) for part in segments):
            suggested = f"Juzgado de Primera Instancia en lo {subject} de {number.group(1)}ª Nominación"
            if any(part.casefold() == "rosario" for part in segments):
                suggested += " de Rosario"
        elif any(re.search(r"c[aá]mara federal", part, re.I) for part in segments):
            if any(part.casefold() == "rosario" for part in segments):
                suggested = "Cámara Federal de Rosario"
        courts[label.casefold()] = {"label": label, "path": path, "suggested": suggested}
    catalogued: set[str] = set()
    if DB.is_file():
        with sqlite3.connect(f"file:{DB.resolve()}?mode=ro", uri=True) as connection:
            if connection.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='documents'").fetchone():
                catalogued = {str(row[0]).strip() for row in connection.execute(
                    "SELECT DISTINCT court FROM documents WHERE court IS NOT NULL AND TRIM(court)<>''"
                )}
    return {"courts": sorted(courts.values(), key=lambda item: item["label"].casefold()),
            "catalogued": sorted(catalogued, key=str.casefold)}


def folders(query: str = "") -> list[str]:
    if not CATALOG.is_file():
        raise FileNotFoundError(f"No existe el catálogo: {CATALOG}")
    found: set[str] = set()
    with sqlite3.connect(f"file:{CATALOG.resolve()}?mode=ro", uri=True) as connection:
        rows = connection.execute("SELECT path FROM documents WHERE category='Jurisprudencia' AND COALESCE(is_deleted,0)=0")
        for (path,) in rows:
            parent = str(Path(str(path)).parent)
            if query.casefold() in parent.casefold():
                found.add(parent)
    return sorted(found, key=str.casefold)[:120]


def preview(folder: str) -> dict[str, Any]:
    folder = folder.strip()
    if not folder or folder in {".", ".."}:
        raise ValueError("Elegí una carpeta de Jurisprudencia.")
    selected = candidates(CATALOG, DB, "", MAX_SELECTION + 1, folder=folder, runs_root=RUNS)
    return {"folder": folder, "items": selected[:MAX_SELECTION], "total": min(len(selected), MAX_SELECTION),
            "truncated": len(selected) > MAX_SELECTION, "limit": MAX_SELECTION}


def _job_dir(job_id: str) -> Path:
    if not job_id.startswith("std-ui-") or any(c not in "abcdefghijklmnopqrstuvwxyz0123456789-" for c in job_id):
        raise ValueError("Identificador de lote inválido.")
    return RUNS / "ui_jobs" / job_id


def _write(job: dict[str, Any]) -> None:
    directory = _job_dir(job["job_id"])
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / "job.json"
    temporary = path.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(job, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def status(job_id: str) -> dict[str, Any]:
    path = _job_dir(job_id) / "job.json"
    if not path.is_file():
        raise ValueError("El lote no existe en esta instalación.")
    job = json.loads(path.read_text(encoding="utf-8"))
    if job.get("phase") in {"created", "preparing", "submitting", "extracting", "validating", "preparing_relations",
                            "relations_submitting", "relations_extracting"} and job_id not in _ACTIVE:
        action = "resume_prepare" if job["phase"] in {"created", "preparing"} else (
            "relations" if job["phase"].startswith("relations_") else "send")
        job["phase"] = "error"
        job["error"] = "El servicio se cerró durante el trabajo. Podés reanudar la etapa."
        job["error_action"] = action
        _write(job)
    pending = 0
    for run_id in job.get("run_ids") or []:
        if not run_id:
            continue
        state_path = RUNS / run_id / "state.json"
        if not state_path.is_file():
            continue
        stage = json.loads(state_path.read_text(encoding="utf-8")).get("stage")
        if stage == "extraction_ready_to_submit" and not (RUNS / run_id / "extraction_batch" / "batch_state.json").is_file():
            pending += 1
    job["api_parts_pending"] = pending
    return job


def recent() -> list[dict[str, Any]]:
    root = RUNS / "ui_jobs"
    if not root.is_dir():
        return []
    jobs = []
    for path in root.glob("std-ui-*/job.json"):
        try:
            item = json.loads(path.read_text(encoding="utf-8"))
            jobs.append({key: item.get(key) for key in ("job_id", "folder", "phase", "total", "standards", "step", "steps", "percent")})
        except (ValueError, OSError):
            continue
    return sorted(jobs, key=lambda job: job["job_id"], reverse=True)[:15]


def _update(job: dict[str, Any], *, phase: str, step: int, step_percent: int = 0,
            message: str = "", file: str = "", **extra: Any) -> None:
    if phase != "error":
        job["error"] = ""
        job["error_action"] = ""
    job.update(extra)
    job.update(phase=phase, step=step, step_percent=max(0, min(100, int(step_percent))),
               percent=min(100, round(100 * ((step-1) + max(0, min(100, step_percent))/100) / job["steps"])),
               message=message, file=file)
    if message and (not job["log"] or job["log"][-1] != message):
        job["log"] = (job["log"] + [message])[-120:]
    _write(job)


def _pipeline(run_id: str, job: dict[str, Any], step: int, stage_name: str) -> StandardsPipeline:
    def callback(event: dict[str, Any]) -> None:
        current, total = int(event.get("current") or 0), int(event.get("total") or 1)
        percent = round(100 * current / total)
        filename = str(event.get("file") or "")
        job["standards"] = int(job.get("completed_standards") or 0) + int(event.get("standards") or 0)
        job["file_standards"] = int(event.get("file_standards") or 0)
        job["without_standards"] = len(job.get("without_standards_files") or []) + int(event.get("without_standards") or 0)
        job["processed_files"] = min(job["total"], int(job.get("completed_files") or 0) + current)
        phase={"Preparación": "preparing", "Validación": "validating", "Relaciones": "preparing_relations"}.get(stage_name, stage_name)
        finding = " · sin estándar generalizable" if event.get("stage") == "validate" and "file_standards" in event and not job["file_standards"] else ""
        _update(job, phase=phase, step=step, step_percent=percent, file=filename,
                message=f"{stage_name}: {current}/{total} · {filename}{finding}")
    return StandardsPipeline(repo_root=ROOT, db_path=DB, runs_root=RUNS, run_id=run_id, progress=callback)


def _run_worker(job_id: str, action: str) -> None:
    job = status(job_id)
    try:
        if action == "prepare":
            paths = (_job_dir(job_id) / "selection.txt").read_text(encoding="utf-8").splitlines()
            for index in range(job["chunks"]):
                subset = paths[index*CHUNK:(index+1)*CHUNK]
                run_id = f"{job_id}-part-{index+1:03}"
                prior = RUNS / run_id / "state.json"
                if prior.exists():
                    stage = json.loads(prior.read_text(encoding="utf-8")).get("stage")
                    if stage != "extraction_ready_to_submit":
                        run_id += "-retry-" + uuid.uuid4().hex[:6]
                job["run_ids"][index] = run_id
                selection = _job_dir(job_id) / f"part-{index+1:03}.txt"
                selection.write_text("\n".join(subset) + "\n", encoding="utf-8")
                step = 2 + index
                _update(job, phase="preparing", step=step, message=f"Preparando parte {index+1}/{job['chunks']}")
                pipeline = _pipeline(run_id, job, step, "Preparación")
                if not (RUNS / run_id / "state.json").exists():
                    pipeline.prepare(catalog_path=CATALOG, paths_file=selection,
                                     court=job.get("court") or None, model=job["model"],
                                     reasoning_effort=job["reasoning_effort"])
                _update(job, phase="preparing", step=step, step_percent=100,
                        message=f"Parte {index+1}/{job['chunks']} preparada")
            _update(job, phase="ready_to_send", step=1+job["chunks"], step_percent=100,
                    message=f"{job['total']} fallos preparados. El envío a la API espera tu orden.")
        elif action == "send":
            for index, run_id in enumerate(job["run_ids"]):
                step = 2+job["chunks"]+index*2
                pipeline = _pipeline(run_id, job, step+1, "Validación")
                stage = pipeline.load_state().get("stage")
                if stage == "extraction_ready_to_submit":
                    _update(job, phase="submitting", step=step, message=f"Enviando parte {index+1}/{job['chunks']} a la API")
                    if (pipeline.run_dir / "extraction_batch" / "batch_state.json").exists():
                        pipeline._transition("extraction_submitted")
                    else:
                        pipeline.submit_extraction()
                    stage = "extraction_submitted"
                if stage == "extraction_submitted":
                    while True:
                        pipeline.batch_status()
                        batch = json.loads((pipeline.run_dir / "extraction_batch" / "batch_state.json").read_text(encoding="utf-8"))
                        counts = batch.get("request_counts") or {}
                        done = int(counts.get("completed") or 0)
                        failed = int(counts.get("failed") or 0)
                        total = len((_job_dir(job_id) / f"part-{index+1:03}.txt").read_text(encoding="utf-8").splitlines())
                        _update(job, phase="extracting", step=step, step_percent=round(100*(done+failed)/max(total,1)),
                                message=f"API, parte {index+1}/{job['chunks']}: {done}/{total} respuestas · {failed} fallidas",
                                api_status=batch.get("status"), requests_completed=done, requests_failed=failed, file="")
                        if batch.get("status") == "completed":
                            if failed:
                                raise RuntimeError(f"La parte {index+1} terminó con {failed} solicitudes fallidas. Revisá el lote antes de reintentar.")
                            break
                        if batch.get("status") in {"failed", "expired", "cancelled"}:
                            raise RuntimeError(f"La API cerró la parte {index+1}: {batch.get('status')}")
                        time.sleep(20)
                    _update(job, phase="validating", step=step+1, message=f"Validando parte {index+1}/{job['chunks']}")
                    result = pipeline.collect_extraction(prepare_relations=False)
                    stage = result.get("stage")
                if stage == "extraction_collected":
                    _update(job, phase="validating", step=step+1,
                            message=f"Reanudando validación de la parte {index+1}/{job['chunks']}")
                    stage = pipeline._validate_import_and_prepare_relations(prepare_relations=False).get("stage")
                if stage != "standards_imported":
                    raise RuntimeError(f"La parte {index+1} quedó en un estado inesperado: {stage}")
                validation = pipeline.load_state().get("validation") or {}
                empty_runs = job.setdefault("without_standards_by_run", {})
                empty_runs[run_id] = validation.get("documents_without_standards") or []
                job["without_standards_files"] = [item for rows in empty_runs.values() for item in rows]
                job["without_standards"] = len(job["without_standards_files"])
                counted = job.setdefault("counted_run_ids", [])
                if run_id not in counted:
                    job["completed_standards"] = int(job.get("completed_standards") or 0) + int(validation.get("standards") or 0)
                    counted.append(run_id)
                job["standards"] = job["completed_standards"]
                job["completed_files"] = min(job["total"], (index+1)*CHUNK)
                _update(job, phase="validating", step=step+1, step_percent=100,
                        message=f"Parte {index+1}/{job['chunks']} importada · {validation.get('standards',0)} estándares")
            step = job["steps"]
            _update(job, phase="preparing_relations", step=step, message="Preparando comparaciones de relaciones")
            final = _pipeline(job["run_ids"][-1], job, step, "Relaciones")
            result = final.prepare_relations()
            ready = result.get("stage") == "relations_ready_to_submit"
            _update(job, phase="relations_ready" if ready else "completed", step=step,
                    step_percent=100, relation_candidates=int(result.get("relation_candidates") or 0),
                    message=(f"{result.get('relation_candidates',0)} relaciones preparadas; envío pendiente de tu orden."
                             if ready else "Extracción completa. No hay relaciones nuevas."))
        elif action == "relations":
            pipeline = _pipeline(job["run_ids"][-1], job, job["steps"], "Relaciones")
            stage = pipeline.load_state().get("stage")
            if stage == "relations_ready_to_submit":
                _update(job, phase="relations_submitting", step=job["steps"], message="Enviando relaciones")
                if (pipeline.run_dir / "relations_batch" / "batch_state.json").exists():
                    pipeline._transition("relations_submitted")
                else:
                    pipeline.submit_relations()
            while True:
                pipeline.batch_status()
                batch = json.loads((pipeline.run_dir / "relations_batch" / "batch_state.json").read_text(encoding="utf-8"))
                counts = batch.get("request_counts") or {}
                total = int(job.get("relation_candidates") or 0)
                done, failed = int(counts.get("completed") or 0), int(counts.get("failed") or 0)
                _update(job, phase="relations_extracting", step=job["steps"],
                        step_percent=round(100*(done+failed)/max(total,1)),
                        message=f"Relaciones: {done}/{total} respuestas · {failed} fallidas")
                if batch.get("status") == "completed":
                    if failed:
                        raise RuntimeError(f"Hubo {failed} comparaciones fallidas.")
                    break
                if batch.get("status") in {"failed", "expired", "cancelled"}:
                    raise RuntimeError(f"La API cerró las relaciones: {batch.get('status')}")
                time.sleep(20)
            result = pipeline.collect_relations()
            _update(job, phase="completed", step=job["steps"], step_percent=100,
                    message=f"Trabajo completo · {job['standards']} estándares · {result.get('relation_candidates',0)} relaciones propuestas")
    except Exception as error:
        terminal = "fallidas" in str(error) or "inválidas" in str(error) or "cerró" in str(error)
        _update(job, phase="error", step=max(1, int(job.get("step") or 1)),
                step_percent=int(job.get("step_percent") or 0), message=str(error), error=str(error),
                error_action="" if terminal else {"prepare": "resume_prepare", "send": "send", "relations": "relations"}[action])
    finally:
        with _LOCK:
            _ACTIVE.discard(job_id)


def _start(job_id: str, action: str) -> dict[str, Any]:
    with _LOCK:
        if _ACTIVE:
            raise ValueError("Ya hay un lote de estándares en ejecución.")
        _ACTIVE.add(job_id)
    threading.Thread(target=_run_worker, args=(job_id, action), daemon=True, name="lexia-standards-batch").start()
    return status(job_id)


def prepare(payload: dict[str, Any]) -> dict[str, Any]:
    with _LOCK:
        if _ACTIVE:
            raise ValueError("Ya hay un lote de estándares en ejecución.")
    folder = str(payload.get("folder") or "").strip()
    court_mode = str(payload.get("court_mode") or ("manual" if payload.get("court") else "api"))
    if court_mode not in {"manual", "api"}:
        raise ValueError("Elegí tribunal único o extracción del tribunal por la API.")
    court = str(payload.get("court") or "").strip() if court_mode == "manual" else ""
    if court_mode == "manual" and not court:
        raise ValueError("Indicá el tribunal que dictó todos los fallos, o elegí extracción por la API.")
    selected = payload.get("paths")
    if not isinstance(selected, list) or not selected or len(selected) > MAX_SELECTION:
        raise ValueError(f"Elegí entre 1 y {MAX_SELECTION} fallos.")
    allowed = set(preview(folder)["items"])
    paths = list(dict.fromkeys(str(path) for path in selected))
    if len(paths) != len(selected) or any(path not in allowed for path in paths):
        raise ValueError("La selección cambió; revisá de nuevo los fallos disponibles.")
    job_id = "std-ui-" + time.strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:6]
    chunks = math.ceil(len(paths)/CHUNK)
    job = {"job_id": job_id, "folder": folder, "phase": "created", "total": len(paths),
           "chunks": chunks, "run_ids": [None]*chunks, "model": "gpt-5.6-luna",
           "reasoning_effort": "medium", "court": court, "court_mode": court_mode,
           "steps": 2+3*chunks, "step": 1, "step_percent": 100, "percent": 0,
           "standards": 0, "completed_standards": 0, "completed_files": 0, "processed_files": 0,
           "without_standards": 0, "without_standards_files": [], "without_standards_by_run": {},
           "file_standards": 0, "file": "", "message": "Selección lista", "log": ["Selección lista"],
           "relation_candidates": 0, "error": ""}
    directory = _job_dir(job_id)
    directory.mkdir(parents=True, exist_ok=False)
    (directory / "selection.txt").write_text("\n".join(paths)+"\n", encoding="utf-8")
    _write(job)
    return _start(job_id, "prepare")


def act(job_id: str, action: str) -> dict[str, Any]:
    job = status(job_id)
    allowed = {"send": {"ready_to_send"}, "relations": {"relations_ready"},
               "resume_prepare": {"created", "preparing"}}
    if action not in allowed or job["phase"] not in allowed[action]:
        if job["phase"] != "error" or job.get("error_action") != action:
            raise ValueError("La etapa actual no admite esta acción.")
    if action == "send" and not all(job["run_ids"]):
        raise ValueError("La preparación todavía no terminó.")
    return _start(job_id, "prepare" if action == "resume_prepare" else action)
