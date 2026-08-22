from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from datetime import datetime
import json
import os
import secrets
import shutil
import threading
import time
import uuid
from types import SimpleNamespace

from config.settings import SETTINGS


_BRIDGE_LOCK = threading.RLock()
_BRIDGE_SERVER = None
_BRIDGE_THREAD = None
_MAINTENANCE_DIAGNOSTIC_LOCK = threading.RLock()
_MAINTENANCE_DIAGNOSTIC = {
    "running": False,
    "status": "Sin diagnóstico en curso",
    "started_at": "",
    "finished_at": "",
    "report": None,
    "error": "",
}


def _tail_text_file(path: Path, limit: int = 60) -> list[str]:
    """Read only the final part of a runtime log, even when it is very large."""
    if limit <= 0 or not path.is_file():
        return []
    try:
        with path.open("rb") as stream:
            stream.seek(0, os.SEEK_END)
            size = stream.tell()
            stream.seek(max(0, size - 262_144))
            raw = stream.read().decode("utf-8", errors="replace")
        return [line for line in raw.splitlines() if line.strip()][-limit:]
    except OSError:
        return []


def _maintenance_monitor(
    autosync: dict,
    ocr: dict,
    history: list[dict],
    recent_errors: list[dict],
    limit: int = 80,
) -> list[str]:
    """Build a bounded technical trace from live state and persistent logs."""
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    sync_total = int(autosync.get("total", 0) or 0)
    sync_processed = int(autosync.get("processed", 0) or 0)
    ocr_total = int(ocr.get("total", 0) or 0)
    ocr_processed = int(ocr.get("processed", 0) or 0)
    lines = [
        (
            f"{now} | AUTOSYNC | {autosync.get('phase', 'idle')} | "
            f"{autosync.get('status', 'Sin estado')} | "
            f"{sync_processed}/{sync_total} | "
            f"{autosync.get('current_file', '')}"
        ),
        (
            f"{now} | OCR | {ocr.get('stage', 'idle')} | "
            f"running={bool(ocr.get('running', False))} | "
            f"document={ocr.get('document_position', 0)}/{ocr_total} | "
            f"page={ocr.get('current_page', 0)}/{ocr.get('total_pages', 0)} | "
            f"completed_documents={ocr_processed} | "
            f"pending={int(ocr.get('pending', 0) or 0)} | "
            f"processing={int(ocr.get('processing', 0) or 0)} | "
            f"errors={int(ocr.get('error', 0) or 0)} | "
            f"{ocr.get('document_name', '')} | {ocr.get('current_file', '')}"
        ),
    ]
    for item in history[:12]:
        lines.append(
            f"{item.get('created_at', '')} | MANTENIMIENTO | "
            f"{item.get('action', '')} | {item.get('status', '')} | "
            f"{item.get('message', '')}"
        )
    for item in recent_errors[:8]:
        lines.append(
            f"{item.get('updated_at', '')} | {item.get('source', 'ERROR')} | "
            f"{item.get('name', '')} | {item.get('error', '')}"
        )
    runtime = _project_root() / "runtime"
    for filename in ("ocr_diagnostic.log", "autosync.log", "lexia.log"):
        for line in _tail_text_file(runtime / filename, limit=30):
            lines.append(f"{filename} | {line}")
    return lines[-limit:]


def _start_maintenance_diagnostic(application) -> dict:
    """Start the expensive health report without blocking the UI bridge."""
    with _MAINTENANCE_DIAGNOSTIC_LOCK:
        if _MAINTENANCE_DIAGNOSTIC["running"]:
            return {
                "ok": True,
                "action": "diagnostic",
                "started": False,
                "message": "El diagnóstico ya está en ejecución.",
            }
        _MAINTENANCE_DIAGNOSTIC.update({
            "running": True,
            "status": "Comprobando disco, bases e índices…",
            "started_at": datetime.now().isoformat(timespec="seconds"),
            "finished_at": "",
            "report": None,
            "error": "",
        })

    def worker() -> None:
        try:
            report = application.health.report()
            with _MAINTENANCE_DIAGNOSTIC_LOCK:
                _MAINTENANCE_DIAGNOSTIC.update({
                    "running": False,
                    "status": "Diagnóstico finalizado",
                    "finished_at": datetime.now().isoformat(timespec="seconds"),
                    "report": report,
                    "error": "",
                })
            _record_maintenance_action(application, "diagnostic", {
                "message": "Diagnóstico finalizado.",
            })
        except Exception as error:
            with _MAINTENANCE_DIAGNOSTIC_LOCK:
                _MAINTENANCE_DIAGNOSTIC.update({
                    "running": False,
                    "status": "El diagnóstico terminó con error",
                    "finished_at": datetime.now().isoformat(timespec="seconds"),
                    "report": None,
                    "error": str(error),
                })
            _record_maintenance_action(
                application,
                "diagnostic",
                {"message": str(error)},
                status="error",
            )

    threading.Thread(
        target=worker,
        name="LexIA-Maintenance-Diagnostic",
        daemon=True,
    ).start()
    return {
        "ok": True,
        "action": "diagnostic",
        "started": True,
        "message": "Diagnóstico iniciado en segundo plano.",
    }


def _maintenance_ocr_status(application) -> dict:
    """Expose document and page-level OCR progress from the persistent queue."""
    queue = application.ocr_queue
    state = queue.state()
    stats = queue.stats()
    current_file = str(state.get("current_file", "") or "")
    item = {}
    if current_file:
        try:
            item = queue.repository.get(current_file) or {}
        except Exception:
            item = {}
    total_pages = int(
        state.get("total_pages")
        or item.get("total_pages", 0)
        or 0
    )
    completed_pages = int(
        state.get("completed_pages")
        if state.get("completed_pages") is not None
        else item.get("progress_page", 0)
        or 0
    )
    stage = str(state.get("stage", "idle") or "idle")
    current_page = int(state.get("current_page", 0) or 0)
    if not current_page and stage == "ocr" and total_pages:
        current_page = min(total_pages, completed_pages + 1)
    documents_total = int(state.get("total", 0) or 0)
    documents_processed = int(state.get("processed", 0) or 0)
    return {
        **stats,
        "running": bool(state.get("running", False)),
        "current_file": current_file,
        "document_name": str(
            state.get("document_name")
            or item.get("document_name")
            or (Path(current_file).name if current_file else "")
        ),
        "document_position": (
            min(documents_total, documents_processed + 1)
            if current_file else 0
        ),
        "processed": documents_processed,
        "total": documents_total,
        "stage": stage,
        "stopping": bool(state.get("stopping", False)),
        "message": str(state.get("error", "") or ""),
        "current_page": current_page,
        "completed_pages": completed_pages,
        "total_pages": total_pages,
        "page_percentage": (
            round(100 * completed_pages / total_pages)
            if total_pages else 0
        ),
    }


def _maintenance_live_snapshot(application) -> dict:
    """Fast status for the global sidebar; never scans the catalog."""
    autosync = application.autosync.state()
    ocr = _maintenance_ocr_status(application)
    return {"ok": True, "autosync": autosync, "ocr": ocr}


def _maintenance_snapshot(application) -> dict:
    """Small live projection from the process that owns LexIA services."""
    autosync = application.autosync.state()
    ocr = _maintenance_ocr_status(application)
    ocr_stats = ocr
    config = application.autosync.configuration()
    busy = (
        str(autosync.get("phase", "idle"))
        in {"waiting", "scanning", "indexing", "knowledge"}
        or bool(ocr.get("running", False))
    )
    # The Maintenance monitor never needs recent documents. Avoiding that
    # query, and error sorting while an engine is busy, keeps Refresh fast.
    activity = application.activity_center.snapshot(
        recent_limit=0,
        error_limit=0 if busy else 8,
    )
    problems = []
    if str(autosync.get("phase", "")) == "error" or autosync.get("last_error"):
        problems.append({
            "kind": "AutoSync",
            "message": str(autosync.get("last_error") or "La sincronización requiere revisión."),
            "action": "Revisá el detalle y ejecutá una sincronización manual cuando no haya tareas activas.",
        })
    if int(ocr_stats.get("error", 0) or 0):
        problems.append({
            "kind": "OCR",
            "message": f"Hay {int(ocr_stats.get('error', 0) or 0)} documento(s) con error de OCR.",
            "action": "Procesá la cola OCR; los documentos con error se reintentan sin bloquear la biblioteca.",
        })
    for item in activity.recent_errors[:4]:
        problems.append({
            "kind": str(item.get("source") or "Documento"),
            "message": (
                f"{item.get('name') or 'Documento'}: "
                f"{item.get('error') or 'no se pudo extraer texto'}"
            ),
            "action": "Abrí el documento, verificá que no esté dañado y reintentá la extracción u OCR.",
        })

    try:
        backups = [
            {"name": path.name}
            for path in application.backups.list_backups()[:8]
        ]
    except Exception:
        backups = []

    try:
        history = application.maintenance_history.recent(limit=8)
    except Exception:
        history = []

    try:
        platform = application.platform_info.status()
    except Exception:
        platform = {}

    with _MAINTENANCE_DIAGNOSTIC_LOCK:
        diagnostic = dict(_MAINTENANCE_DIAGNOSTIC)

    sync_phase = str(autosync.get("phase", "idle") or "idle")
    if ocr["running"]:
        operation = {
            "engine": "OCR",
            "function": str(ocr.get("stage") or "ocr"),
            "status": "Procesando OCR",
            "current_file": ocr["current_file"],
            "processed": ocr["processed"],
            "total": ocr["total"],
            "percentage": (
                round(100 * ocr["processed"] / ocr["total"])
                if ocr["total"] else 0
            ),
            "queued": int(ocr.get("pending", 0) or 0),
            "current_page": int(ocr.get("current_page", 0) or 0),
            "total_pages": int(ocr.get("total_pages", 0) or 0),
        }
    elif sync_phase in {"waiting", "scanning", "indexing", "knowledge"}:
        operation = {
            "engine": "AutoSync",
            "function": sync_phase,
            "status": str(autosync.get("status", "AutoSync trabajando") or ""),
            "current_file": str(autosync.get("current_file", "") or ""),
            "processed": int(autosync.get("processed", 0) or 0),
            "total": int(autosync.get("total", 0) or 0),
            "percentage": int(autosync.get("percentage", 0) or 0),
            "queued": max(
                0,
                int(autosync.get("total", 0) or 0)
                - int(autosync.get("processed", 0) or 0),
            ),
        }
    else:
        operation = {
            "engine": "LexIA",
            "function": "idle",
            "status": str(autosync.get("status", "Biblioteca al día") or ""),
            "current_file": "",
            "processed": 0,
            "total": 0,
            "percentage": 0,
            "queued": int(ocr.get("pending", 0) or 0),
        }

    monitor = _maintenance_monitor(
        autosync,
        ocr,
        history,
        activity.recent_errors,
    )

    return {
        "ok": True,
        "live": {
            "autosync": autosync,
            "ocr": ocr,
            "catalog": {
                "documents": int(activity.documents_total),
                "recent_errors": activity.recent_errors,
            },
        },
        "autosync_config": config,
        "ocr_policy": {
            "mode": "manual_queue",
            "description": (
                "Los documentos se incorporan primero; el OCR se procesa "
                "manualmente desde la cola para no demorar la carga."
            ),
        },
        "backups": backups,
        "history": history,
        "operation": operation,
        "monitor": monitor,
        "diagnostic": diagnostic,
        "platform": platform,
        "problems": problems,
        "backup_scope": {
            "database": True,
            "knowledge": True,
            "library": False,
            "qdrant": False,
            "note": (
                "La copia operativa protege las bases y Knowledge. La "
                "biblioteca física y Qdrant requieren una copia hito "
                "separada antes de una migración."
            ),
        },
    }


def _record_maintenance_action(
    application,
    action: str,
    payload: dict,
    status: str = "ok",
) -> dict:
    """Persist the result without letting audit storage block the operation."""
    try:
        application.maintenance_history.record(
            action=action,
            status=status,
            message=str(payload.get("message") or ""),
            details={
                key: value
                for key, value in payload.items()
                if key in {
                    "started", "stopped", "selected", "backup", "config"
                }
            },
        )
    except Exception:
        pass
    return payload


def _maintenance_action(application, body: dict) -> dict:
    """Run an explicit maintenance action against the live services."""
    action = str(body.get("action", "") or "").strip()
    try:
        if action == "autosync-config":
            mode = str(body.get("mode", "") or "").strip().lower()
            schedule_time = str(
                body.get("schedule_time", "03:00") or "03:00"
            ).strip()
            return _record_maintenance_action(application, action, {
                "ok": True,
                "action": action,
                "config": application.autosync.set_configuration(
                    mode, schedule_time
                ),
                "message": "La configuración de AutoSync fue guardada.",
            })
        if action == "autosync-scan":
            result = application.autosync.sync_now()
            return _record_maintenance_action(application, action, {
                "ok": True,
                "action": action,
                "message": str(
                    result.get("status")
                    or "La sincronización fue puesta en cola."
                ),
                "state": application.autosync.state(),
            })
        if action == "autosync-stop-indexing":
            stopped = bool(application.autosync.request_stop_indexing())
            return _record_maintenance_action(application, action, {
                "ok": True, "action": action, "stopped": stopped,
                "message": (
                    "La indexación se detendrá al finalizar el lote actual."
                    if stopped else "No hay una indexación activa para detener."
                ),
            })
        if action == "ocr-start-all":
            queue = application.ocr_queue
            before = queue.stats()
            queue.select_all(True)
            try:
                selected = len(queue.repository.get_selected_paths())
            except Exception:
                selected = int(before.get("pending", 0) or 0)
            started = bool(queue.start_selected())
            current, stats = queue.state(), queue.stats()
            if started:
                message = (
                    f"OCR iniciado: {selected} documento(s) seleccionado(s)."
                )
            elif current.get("running") or int(stats.get("processing", 0) or 0):
                message = "El OCR ya está en ejecución."
            else:
                message = "No hay documentos OCR pendientes para procesar."
            return _record_maintenance_action(application, action, {
                "ok": True, "action": action, "started": started,
                "selected": selected,
                "message": message, "state": current, "stats": stats,
            })
        if action == "ocr-stop":
            stopped = bool(application.ocr_queue.request_stop())
            return _record_maintenance_action(application, action, {
                "ok": True, "action": action, "stopped": stopped,
                "message": (
                    "El OCR se detendrá al finalizar la página actual."
                    if stopped else "No hay un OCR activo para detener."
                ),
            })
        if action == "diagnostic":
            return _start_maintenance_diagnostic(application)
        if action == "backup":
            backup = application.backups.create()
            return _record_maintenance_action(application, action, {
                "ok": True, "action": action, "backup": backup.name,
                "path": str(backup), "message": "Copia operativa creada.",
            })
        raise ValueError("Acción de mantenimiento no reconocida.")
    except Exception as error:
        _record_maintenance_action(
            application,
            action or "unknown",
            {"message": str(error)},
            status="error",
        )
        raise


def _project_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _state_path() -> Path:
    return _project_root() / "runtime" / "ui2_delete_bridge.json"


def _write_state(port: int, token: str) -> None:
    path = _state_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(
        json.dumps(
            {
                "version": 1,
                "host": "127.0.0.1",
                "port": int(port),
                "token": token,
                "pid": os.getpid(),
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    temporary.replace(path)


def _handler_class(application, token):
    # UI2 no debe esperar dentro de una petición HTTP a que termine una
    # investigación. Ambos trabajos usan el motor real de LexIA, pero su
    # estado se consulta desde la interfaz mediante polling liviano.
    study_lock = threading.RLock()
    study_state = {
        "job_id": None,
        "phase": "idle",
        "status": "Sin estudio en curso",
        "percentage": 0,
        "error": None,
        "elapsed_seconds": 0.0,
    }
    study_result = None
    research_lock = threading.RLock()
    research_state = {
        "job_id": None,
        "phase": "idle",
        "status": "Sin investigación en curso",
        "percentage": 0,
        "error": None,
        "elapsed_seconds": 0.0,
    }
    candidates_lock = threading.RLock()
    candidates_state = {
        "job_id": None, "phase": "idle", "status": "Sin búsqueda de fuentes en curso",
        "percentage": 0, "current_step": 0, "total_steps": 4, "error": None, "elapsed_seconds": 0.0,
    }
    candidates_package = None
    package_state = {
        "job_id": None, "phase": "idle", "status": "Sin paquete pendiente",
        "percentage": 0, "error": None, "elapsed_seconds": 0.0,
    }
    package_result = None
    cancelled_candidate_jobs = set()
    paused_candidate_jobs = set()
    candidate_pause_events = {}
    navigator_lock = threading.RLock()
    navigator_operation_state = {
        "job_id": None, "phase": "idle", "status": "Sin operaciones pendientes",
        "operation": "", "processed": 0, "total": 0, "error": None,
    }

    def public_package(package, saved_paths=(), elapsed_seconds=0.0):
        return {
            "title": str(getattr(package, "title", "Contexto LexIA") or "Contexto LexIA"),
            "content": str(getattr(package, "content", "") or ""),
            "saved_paths": [str(path) for path in (saved_paths or [])],
            "elapsed_seconds": round(float(elapsed_seconds or 0.0), 3),
            "source_count": int(getattr(package, "selected_count", 0) or len(getattr(package, "sources", []) or [])),
            "document_count": int(getattr(package, "document_count", 0) or 0),
            "objective": str(getattr(package, "objective", "") or ""),
        }

    def public_source(source, index):
        metadata = getattr(source, "metadata", {}) or {}
        text = " ".join(str(getattr(source, "text", "") or "").split())
        return {
            "index": int(index),
            "name": str(getattr(source, "document_name", "Fuente sin nombre") or "Fuente sin nombre"),
            "path": str(getattr(source, "document_path", "") or ""),
            "category": str(getattr(source, "category", "Sin categoría") or "Sin categoría"),
            "page_label": str(getattr(source, "page_label", "Ubicación no determinada") or "Ubicación no determinada"),
            "snippet": text[:900],
            "court": str(metadata.get("court", "") or ""),
            "date": str(metadata.get("date", "") or ""),
            "score": float(getattr(source, "score", 0) or 0),
        }

    def navigator_safe_path(value, require_exists=True):
        root = Path(SETTINGS.library_path).expanduser().resolve()
        candidate = Path(str(value or "")).expanduser().resolve()
        try:
            candidate.relative_to(root)
        except ValueError as exc:
            raise PermissionError("La operación debe permanecer dentro de la biblioteca LexIA.") from exc
        if require_exists and not candidate.exists():
            raise FileNotFoundError("La carpeta o archivo ya no existe.")
        return candidate

    def navigator_document(old_path, new_path, category):
        state = application.catalog.get_file_state(str(old_path))
        if state is None:
            raise FileNotFoundError("El documento ya no está activo en el catálogo: " + old_path.name)
        stat = new_path.stat()
        return SimpleNamespace(
            name=new_path.name,
            path=new_path,
            category=str(category or state.get("category") or "Sin categoría"),
            extension=new_path.suffix.lower(),
            size=int(stat.st_size),
            modified_ns=int(stat.st_mtime_ns),
        )

    def navigator_commit_relocations(relocations):
        if not relocations:
            return 0
        result = application.catalog.relocate_documents_batch(relocations)
        relocated = int(result.get("relocated", 0) or 0)
        if relocated != len(relocations) or result.get("failed"):
            raise RuntimeError("LexIA no pudo actualizar todas las rutas de los documentos movidos.")
        paths = [(str(old_path), str(document.path)) for old_path, document in relocations]
        # No todos los documentos del catálogo necesariamente tienen entrada en
        # Knowledge. Una ausencia allí no invalida el movimiento ya confirmado
        # en catálogo ni debe revertir el archivo físico.
        try:
            application.knowledge_engine.move_documents(paths)
        except Exception:
            try:
                application.autosync.request_full_scan("navigator_move_knowledge_repair")
            except Exception:
                pass
        new_paths = [str(document.path) for _old_path, document in relocations]
        # Esta pasada sólo completa relocalizaciones de vectores: no recalcula embeddings.
        try:
            application.indexer.run(target_paths=new_paths)
        except Exception:
            try:
                application.autosync.request_full_scan("navigator_move_vector_repair")
            except Exception:
                pass
        try:
            application.autosync._recent_relocation_paths.update(new_paths)
            application.autosync.library_snapshot.apply_changes(
                changed_paths=set(new_paths),
                deleted_paths={str(old_path) for old_path, _document in relocations},
            )
        except Exception:
            # El catálogo ya es consistente; el AutoSync normal puede refrescar el snapshot.
            pass
        return relocated

    def navigator_move_files(paths, destination, destination_category, report):
        destination = navigator_safe_path(destination)
        if not destination.is_dir():
            raise FileNotFoundError("La carpeta de destino ya no existe.")
        sources = [navigator_safe_path(path) for path in paths]
        if not sources or any(not source.is_file() for source in sources):
            raise ValueError("La selección contiene un archivo inválido.")
        targets = [(source, (destination / source.name).resolve()) for source in sources]
        seen = set()
        for source, target in targets:
            if target == source:
                raise ValueError("Uno de los archivos ya pertenece a la carpeta de destino.")
            if target.exists() or str(target).casefold() in seen:
                raise FileExistsError("Ya existe un archivo con ese nombre en la carpeta de destino.")
            seen.add(str(target).casefold())
        moved = []
        try:
            for index, (source, target) in enumerate(targets, start=1):
                report(index - 1, len(targets), "Moviendo archivos…")
                os.replace(source, target)
                moved.append((source, target))
            relocations = [
                (source, navigator_document(source, target, destination_category))
                for source, target in moved
            ]
            relocated = navigator_commit_relocations(relocations)
            report(len(targets), len(targets), "Archivos movidos y relocalizados por LexIA.")
            return {"moved": len(moved), "relocated": relocated}
        except Exception:
            for source, target in reversed(moved):
                try:
                    if target.exists() and not source.exists():
                        os.replace(target, source)
                except Exception:
                    pass
            raise

    def navigator_move_folder(source, destination, destination_category, report):
        source = navigator_safe_path(source)
        destination = navigator_safe_path(destination)
        if not source.is_dir() or not destination.is_dir():
            raise FileNotFoundError("La carpeta de origen o destino ya no existe.")
        target_root = (destination / source.name).resolve()
        if target_root.exists():
            raise FileExistsError("Ya existe una carpeta con ese nombre en el destino.")
        try:
            target_root.relative_to(source)
            raise ValueError("No se puede mover una carpeta dentro de sí misma.")
        except ValueError as exc:
            if str(exc).startswith("No se puede"):
                raise
        source_files = [item for item in source.rglob("*") if item.is_file()]
        report(0, max(1, len(source_files)), "Moviendo carpeta…")
        os.replace(source, target_root)
        moved_pairs = [(old_path, target_root / old_path.relative_to(source)) for old_path in source_files]
        try:
            relocations = []
            for index, (old_path, new_path) in enumerate(moved_pairs, start=1):
                if application.catalog.get_file_state(str(old_path)) is not None:
                    relocations.append((old_path, navigator_document(old_path, new_path, destination_category)))
                report(index, max(1, len(source_files)), "Relocalizando referencias de LexIA…")
            relocated = navigator_commit_relocations(relocations)
            relocated_old = {str(Path(old_path).resolve()) for old_path, _document in relocations}
            unindexed = [str(new_path) for old_path, new_path in moved_pairs if str(Path(old_path).resolve()) not in relocated_old]
            if unindexed:
                application.autosync.reconcile_paths(unindexed)
            return {"moved_folder": str(target_root), "documents": len(source_files), "relocated": relocated}
        except Exception:
            try:
                if target_root.exists() and not source.exists():
                    os.replace(target_root, source)
            except Exception:
                pass
            raise

    def navigator_delete_folder(folder):
        folder = navigator_safe_path(folder)
        if not folder.is_dir():
            raise FileNotFoundError("La carpeta ya no existe.")
        if any(item.is_file() for item in folder.rglob("*")):
            raise RuntimeError("No se puede eliminar una carpeta que contiene archivos.")
        shutil.rmtree(folder)
        return {"deleted_folder": str(folder)}

    def navigator_delete_files(paths, report):
        service = application.secure_document_deletion
        deleted = []
        for index, raw_path in enumerate(paths, start=1):
            path = navigator_safe_path(raw_path)
            report(index - 1, len(paths), "Eliminando archivos de LexIA…")
            service.delete(path)
            deleted.append(str(path))
            report(index, len(paths), "Eliminando archivos de LexIA…")
        return {"deleted": deleted}

    def start_navigator_operation(body):
        if not isinstance(body, dict):
            raise ValueError("La operación del navegador es inválida.")
        operation = str(body.get("operation", "") or "").strip().lower()
        with navigator_lock:
            if navigator_operation_state["phase"] in {"queued", "running"}:
                raise RuntimeError("Hay otra operación del navegador en curso.")
            job_id = uuid.uuid4().hex
            navigator_operation_state.update({
                "job_id": job_id, "phase": "queued", "status": "Preparando operación…",
                "operation": operation, "processed": 0, "total": 0, "error": None,
            })

        def report(processed, total, status):
            with navigator_lock:
                if navigator_operation_state.get("job_id") != job_id:
                    return
                navigator_operation_state.update({
                    "phase": "running", "processed": int(processed), "total": int(total),
                    "status": str(status),
                })

        def worker():
            try:
                report(0, 0, "Preparando operación…")
                if operation == "create_folder":
                    parent = navigator_safe_path(body.get("parent", ""))
                    name = str(body.get("name", "") or "").strip()
                    target = (parent / name).resolve()
                    navigator_safe_path(target, require_exists=False)
                    if target.exists():
                        raise FileExistsError("Ya existe una carpeta con ese nombre.")
                    target.mkdir(parents=False)
                    result = {"created_folder": str(target)}
                elif operation == "delete_folder":
                    result = navigator_delete_folder(body.get("folder", ""))
                elif operation == "move_folder":
                    result = navigator_move_folder(
                        body.get("source", ""), body.get("destination", ""),
                        body.get("destination_category", ""), report,
                    )
                elif operation == "move_files":
                    result = navigator_move_files(
                        body.get("paths") or [], body.get("destination", ""),
                        body.get("destination_category", ""), report,
                    )
                elif operation == "delete_files":
                    result = navigator_delete_files(body.get("paths") or [], report)
                else:
                    raise ValueError("Operación de navegador no reconocida.")
                with navigator_lock:
                    if navigator_operation_state.get("job_id") == job_id:
                        navigator_operation_state.update({
                            "phase": "completed", "status": "Operación completada.",
                            "result": result,
                        })
            except Exception as exc:
                with navigator_lock:
                    if navigator_operation_state.get("job_id") == job_id:
                        navigator_operation_state.update({
                            "phase": "error", "status": "La operación no se pudo completar.",
                            "error": str(exc),
                        })

        threading.Thread(target=worker, name="LexIA-UI2-Navigator-" + job_id[:8], daemon=True).start()
        return {"ok": True, "job_id": job_id, "state": dict(navigator_operation_state)}

    def start_research_candidates(body):
        nonlocal candidates_package, package_result
        query = str(body.get("query", "") or "").strip()
        if not query:
            raise ValueError("Ingresá una consulta jurídica para buscar fuentes.")
        requested_sources = max(1, min(int(body.get("max_sources", 14) or 14), 20))
        depth = str(body.get("depth", "normal") or "normal").strip().lower()
        candidate_limit = {
            "quick": min(12, requested_sources + 4),
            "normal": min(18, requested_sources + 4),
            "complete": 20,
            "exhaustive": 20,
        }.get(depth, min(18, requested_sources + 4))
        candidate_limit = max(requested_sources, candidate_limit)
        with candidates_lock:
            if candidates_state["phase"] in {"queued", "searching", "paused"}:
                raise RuntimeError("Ya hay una búsqueda de fuentes en curso.")
            job_id = uuid.uuid4().hex
            cancelled_candidate_jobs.discard(job_id)
            paused_candidate_jobs.discard(job_id)
            pause_event = threading.Event()
            pause_event.set()
            candidate_pause_events[job_id] = pause_event
            candidates_package = None
            package_result = None
            candidates_state.update({
                "job_id": job_id, "phase": "queued", "status": "Preparando consulta en el motor LexIA...",
                "percentage": 5, "current_step": 0, "total_steps": 4, "error": None, "elapsed_seconds": 0.0,
            })
            package_state.update({
                "job_id": None, "phase": "idle", "status": "Esperando la selección de fuentes...",
                "percentage": 0, "error": None, "elapsed_seconds": 0.0,
            })

        def worker():
            nonlocal candidates_package
            started = time.monotonic()
            try:
                def is_current():
                    with candidates_lock:
                        return (
                            candidates_state.get("job_id") == job_id
                            and job_id not in cancelled_candidate_jobs
                        )

                def wait_if_paused():
                    while True:
                        with candidates_lock:
                            if not is_current():
                                return False
                            paused = job_id in paused_candidate_jobs
                        if not paused:
                            return True
                        # La espera se desbloquea inmediatamente al reanudar;
                        # no queda atada al intervalo de sondeo de la interfaz.
                        pause_event.wait()

                def report(step, status, percentage):
                    if not wait_if_paused():
                        return
                    with candidates_lock:
                        if not is_current():
                            return
                        candidates_state.update({
                            "phase": "searching", "current_step": int(step), "total_steps": 4,
                            "status": str(status), "percentage": int(percentage),
                        })

                with candidates_lock:
                    if not is_current():
                        return
                    candidates_state.update({"phase": "searching", "status": "Iniciando la búsqueda en LexIA...", "percentage": 8, "current_step": 1})
                if not wait_if_paused():
                    return
                package = application.context_builder.build_research_candidates(
                    query=query,
                    facts=str(body.get("facts", "") or ""),
                    objective=str(body.get("objective", "Investigación jurídica") or "Investigación jurídica"),
                    additional_instruction=str(body.get("instruction", "") or ""),
                    candidate_limit=candidate_limit,
                    depth=depth,
                    ordering=str(body.get("ordering", "authority") or "authority"),
                    exclusions=body.get("exclusions") or [],
                    progress_callback=report,
                )
                elapsed = time.monotonic() - started
                if not wait_if_paused():
                    return
                with candidates_lock:
                    if not is_current():
                        return
                    candidates_package = package
                    candidates_state.update({
                        "phase": "completed", "status": "Fuentes listas para revisar",
                        "percentage": 100, "current_step": 4, "total_steps": 4, "error": None, "elapsed_seconds": round(elapsed, 3),
                    })
            except Exception as exc:
                elapsed = time.monotonic() - started
                with candidates_lock:
                    if not is_current():
                        return
                    candidates_state.update({
                        "phase": "error", "status": "La búsqueda de fuentes produjo un error",
                        "percentage": 100, "current_step": candidates_state.get("current_step", 0), "total_steps": 4, "error": str(exc), "elapsed_seconds": round(elapsed, 3),
                    })

        threading.Thread(target=worker, name="LexIA-UI2-Candidates-" + job_id[:8], daemon=True).start()
        return {"ok": True, "job_id": job_id, "state": dict(candidates_state)}

    def cancel_research_candidates():
        nonlocal candidates_package, package_result
        with candidates_lock:
            job_id = candidates_state.get("job_id")
            if job_id:
                cancelled_candidate_jobs.add(job_id)
                paused_candidate_jobs.discard(job_id)
                event = candidate_pause_events.get(job_id)
                if event is not None:
                    event.set()
            candidates_package = None
            package_result = None
            candidates_state.update({
                "phase": "cancelled", "status": "Investigación cancelada",
                "percentage": 0, "current_step": 0, "total_steps": 4,
                "error": None, "elapsed_seconds": 0.0,
            })
            package_state.update({
                "job_id": None, "phase": "idle", "status": "Esperando la selección de fuentes...",
                "percentage": 0, "error": None, "elapsed_seconds": 0.0,
            })
            return {"ok": True, "state": dict(candidates_state)}

    def pause_research_candidates():
        with candidates_lock:
            job_id = candidates_state.get("job_id")
            if not job_id or candidates_state.get("phase") not in {"queued", "searching"}:
                raise RuntimeError("No hay una investigación activa para pausar.")
            paused_candidate_jobs.add(job_id)
            event = candidate_pause_events.get(job_id)
            if event is not None:
                event.clear()
            candidates_state.update({"phase": "paused", "status": "Investigación pausada"})
            return {"ok": True, "state": dict(candidates_state)}

    def resume_research_candidates():
        with candidates_lock:
            job_id = candidates_state.get("job_id")
            if not job_id or candidates_state.get("phase") != "paused":
                raise RuntimeError("No hay una investigación pausada para reanudar.")
            paused_candidate_jobs.discard(job_id)
            event = candidate_pause_events.get(job_id)
            if event is not None:
                event.set()
            candidates_state.update({"phase": "searching", "status": "Reanudando investigación..."})
            return {"ok": True, "state": dict(candidates_state)}

    def candidates_result():
        with candidates_lock:
            if candidates_state["phase"] != "completed" or candidates_package is None:
                raise RuntimeError("Las fuentes todavía no están listas.")
            sources = [public_source(source, index) for index, source in enumerate(candidates_package.sources)]
            return {
                "ok": True, "job_id": candidates_state["job_id"], "result": {
                    "sources": sources,
                    "source_count": len(sources),
                    "document_count": int(getattr(candidates_package, "document_count", 0) or 0),
                    "elapsed_seconds": candidates_state["elapsed_seconds"],
                },
            }

    def start_selected_package(body):
        nonlocal package_result
        with candidates_lock:
            if candidates_state["phase"] != "completed" or candidates_package is None:
                raise RuntimeError("Primero terminá de recuperar las fuentes.")
            if str(body.get("candidates_job_id", "") or "") != str(candidates_state["job_id"]):
                raise RuntimeError("La selección ya no corresponde a la última consulta.")
            raw_indices = body.get("selected_indices") or []
            if not isinstance(raw_indices, list):
                raise ValueError("La selección de fuentes no es válida.")
            selected = []
            seen = set()
            for value in raw_indices:
                index = int(value)
                if 0 <= index < len(candidates_package.sources) and index not in seen:
                    selected.append(index)
                    seen.add(index)
            if not selected:
                raise ValueError("Seleccioná al menos una fuente para preparar el paquete.")
            if package_state["phase"] in {"queued", "building", "saving"}:
                raise RuntimeError("Ya se está preparando un paquete de investigación.")
            job_id = uuid.uuid4().hex
            package_result = None
            package_state.update({
                "job_id": job_id, "phase": "queued", "status": "Preparando el paquete con las fuentes seleccionadas...",
                "percentage": 10, "error": None, "elapsed_seconds": 0.0,
            })

        def worker():
            nonlocal package_result
            started = time.monotonic()
            try:
                with candidates_lock:
                    package_state.update({"phase": "building", "status": "Construyendo el paquete de investigación...", "percentage": 55})
                curated = application.context_builder.curate_package(candidates_package, selected)
                with candidates_lock:
                    package_state.update({"phase": "saving", "status": "Guardando el paquete de investigación...", "percentage": 85})
                saved_paths = application.context_builder.save(curated)
                elapsed = time.monotonic() - started
                with candidates_lock:
                    package_result = public_package(curated, saved_paths, elapsed)
                    package_state.update({
                        "phase": "completed", "status": "Paquete listo para usar en ChatGPT",
                        "percentage": 100, "error": None, "elapsed_seconds": round(elapsed, 3),
                    })
            except Exception as exc:
                elapsed = time.monotonic() - started
                with candidates_lock:
                    package_state.update({
                        "phase": "error", "status": "No se pudo preparar el paquete",
                        "percentage": 100, "error": str(exc), "elapsed_seconds": round(elapsed, 3),
                    })

        threading.Thread(target=worker, name="LexIA-UI2-Package-" + job_id[:8], daemon=True).start()
        return {"ok": True, "job_id": job_id, "state": dict(package_state)}

    def start_study(body):
        nonlocal study_result
        source = Path(str(body.get("path", "") or "")).expanduser().resolve()
        if not source.is_file():
            raise FileNotFoundError("El archivo indicado no existe.")
        library_root = Path(SETTINGS.library_path).expanduser().resolve()
        source.relative_to(library_root)

        with study_lock:
            if study_state["phase"] in {"queued", "building", "saving"}:
                raise RuntimeError("Ya hay un estudio de archivo en curso.")
            job_id = uuid.uuid4().hex
            study_result = None
            study_state.update({
                "job_id": job_id,
                "phase": "queued",
                "status": "Preparando el estudio del archivo...",
                "percentage": 5,
                "error": None,
                "elapsed_seconds": 0.0,
            })

        def worker():
            nonlocal study_result
            started = time.monotonic()
            try:
                with study_lock:
                    study_state.update({
                        "phase": "building",
                        "status": "Analizando el documento con el motor de LexIA...",
                        "percentage": 45,
                    })
                package = application.context_builder.build_documents_package(
                    documents=[(source, source.name)],
                    objective=str(body.get("objective", "Investigación jurídica") or "Investigación jurídica"),
                    instruction=str(body.get("instruction", "") or ""),
                    document_type=str(body.get("document_type", "Detección automática") or "Detección automática"),
                )
                package.title = "Analisis_" + source.stem
                with study_lock:
                    study_state.update({
                        "phase": "saving",
                        "status": "Guardando el contexto del estudio...",
                        "percentage": 85,
                    })
                saved_paths = application.context_builder.save(package)
                elapsed = time.monotonic() - started
                with study_lock:
                    study_result = public_package(package, saved_paths, elapsed)
                    study_state.update({
                        "phase": "completed",
                        "status": "Estudio listo para continuar la investigación",
                        "percentage": 100,
                        "error": None,
                        "elapsed_seconds": round(elapsed, 3),
                    })
            except Exception as exc:
                elapsed = time.monotonic() - started
                with study_lock:
                    study_state.update({
                        "phase": "error",
                        "status": "El estudio produjo un error",
                        "percentage": 100,
                        "error": str(exc),
                        "elapsed_seconds": round(elapsed, 3),
                    })

        threading.Thread(
            target=worker, name="LexIA-UI2-Study-" + job_id[:8], daemon=True,
        ).start()
        return {"ok": True, "job_id": job_id, "state": dict(study_state)}

    def start_research(body):
        with research_lock:
            if research_state["phase"] in {"queued", "starting"}:
                raise RuntimeError("Ya hay una investigación en curso.")
            job_id = uuid.uuid4().hex
            research_state.update({
                "job_id": job_id,
                "phase": "starting",
                "status": "Conectando el motor de investigación...",
                "percentage": 3,
                "error": None,
                "elapsed_seconds": 0.0,
            })

        def worker():
            try:
                service = application.context_build_jobs
                service.clear_result()
                actual_id = service.start_job(
                    query=str(body.get("query", "") or ""),
                    facts=str(body.get("facts", "") or ""),
                    objective=str(body.get("objective", "Investigación jurídica") or "Investigación jurídica"),
                    additional_instruction=str(body.get("instruction", "") or ""),
                    max_sources=max(1, min(int(body.get("max_sources", 14) or 14), 30)),
                )
                with research_lock:
                    research_state.update({"job_id": actual_id, "phase": "queued", "status": "Preparando investigación...", "percentage": 5})
            except Exception as exc:
                with research_lock:
                    research_state.update({"phase": "error", "status": "La investigación produjo un error", "percentage": 100, "error": str(exc)})

        threading.Thread(
            target=worker, name="LexIA-UI2-Research-" + job_id[:8], daemon=True,
        ).start()
        return {"ok": True, "job_id": job_id, "state": dict(research_state)}

    def current_research_state():
        service = getattr(application, "_context_build_jobs", None)
        if service is None:
            with research_lock:
                return dict(research_state)
        try:
            state = service.state()
        except Exception:
            with research_lock:
                return dict(research_state)
        with research_lock:
            if research_state["phase"] == "starting" and state.get("phase") == "idle":
                return dict(research_state)
            research_state.update(state)
            return dict(research_state)

    class DeleteBridgeHandler(BaseHTTPRequestHandler):
        server_version = "LexIA-Core-Bridge/1.1"

        def log_message(self, _format, *_args):
            return

        def _json(self, payload, status=200):
            raw = json.dumps(payload, ensure_ascii=False, default=str).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(raw)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(raw)

        def _authorized(self):
            supplied = str(self.headers.get("X-LexIA-Delete-Token", "") or "")
            return bool(supplied) and secrets.compare_digest(supplied, token)

        def _body(self):
            length = int(self.headers.get("Content-Length", "0") or 0)
            raw = self.rfile.read(length) if length else b"{}"
            value = json.loads(raw.decode("utf-8"))
            if not isinstance(value, dict):
                raise ValueError("La solicitud debe ser un objeto JSON.")
            return value

        def do_GET(self):
            if not self._authorized():
                return self._json({"ok": False, "error": "Acceso denegado."}, 403)

            if self.path == "/api/delete-file-status":
                try:
                    state = application.secure_document_deletion.state()
                    return self._json({
                        "ok": True,
                        "implementation": "SecureDocumentDeletionService",
                        "same_classic_process": True,
                        "state": state,
                    })
                except Exception as exc:
                    return self._json({"ok": False, "error": str(exc)}, 500)

            if self.path == "/api/health":
                return self._json({
                    "ok": True,
                    "implementation": "SecureDocumentDeletionService",
                    "same_classic_process": True,
                })

            if self.path == "/api/maintenance-snapshot":
                try:
                    payload = _maintenance_snapshot(application)
                    payload["same_classic_process"] = True
                    return self._json(payload)
                except Exception as exc:
                    return self._json({"ok": False, "error": str(exc)}, 500)

            if self.path == "/api/maintenance-live":
                try:
                    payload = _maintenance_live_snapshot(application)
                    payload["same_classic_process"] = True
                    return self._json(payload)
                except Exception as exc:
                    return self._json({"ok": False, "error": str(exc)}, 500)

            if self.path == "/api/study-status":
                with study_lock:
                    return self._json({"ok": True, "state": dict(study_state)})

            if self.path == "/api/study-result":
                with study_lock:
                    if study_state["phase"] != "completed" or study_result is None:
                        return self._json({"ok": False, "error": "El estudio todavía no está listo."}, 409)
                    return self._json({"ok": True, "result": dict(study_result)})

            if self.path == "/api/research-status":
                return self._json({"ok": True, "state": current_research_state()})

            if self.path == "/api/research-result":
                state = current_research_state()
                service = getattr(application, "_context_build_jobs", None)
                result = service.result() if service is not None else None
                if state.get("phase") != "completed" or result is None:
                    return self._json({"ok": False, "error": "La investigación todavía no está lista."}, 409)
                return self._json({"ok": True, "result": public_package(result.package, result.saved_paths, result.elapsed_seconds)})

            if self.path == "/api/research-candidates-status":
                with candidates_lock:
                    return self._json({"ok": True, "state": dict(candidates_state)})

            if self.path == "/api/research-candidates-result":
                try:
                    return self._json(candidates_result())
                except RuntimeError as exc:
                    return self._json({"ok": False, "error": str(exc)}, 409)

            if self.path == "/api/research-package-status":
                with candidates_lock:
                    return self._json({"ok": True, "state": dict(package_state)})

            if self.path == "/api/research-package-result":
                with candidates_lock:
                    if package_state["phase"] != "completed" or package_result is None:
                        return self._json({"ok": False, "error": "El paquete todavía no está listo."}, 409)
                    return self._json({"ok": True, "result": dict(package_result)})

            if self.path == "/api/navigator-operation-status":
                with navigator_lock:
                    return self._json({"ok": True, "state": dict(navigator_operation_state)})

            return self._json({"ok": False, "error": "Ruta no encontrada."}, 404)

        def do_POST(self):
            if not self._authorized():
                return self._json({"ok": False, "error": "Acceso denegado."}, 403)
            if self.path not in {"/api/delete-file", "/api/import-files", "/api/study-document", "/api/study-start", "/api/research-start", "/api/research-candidates-start", "/api/research-candidates-cancel", "/api/research-candidates-pause", "/api/research-candidates-resume", "/api/research-package-start", "/api/navigator-operation", "/api/maintenance-action"}:
                return self._json({"ok": False, "error": "Ruta no encontrada."}, 404)

            try:
                body = self._body()
                if self.path == "/api/maintenance-action":
                    payload = _maintenance_action(application, body)
                    payload["same_classic_process"] = True
                    return self._json(payload)
                if self.path == "/api/study-start":
                    return self._json(start_study(body), 202)
                if self.path == "/api/research-start":
                    return self._json(start_research(body), 202)
                if self.path == "/api/research-candidates-start":
                    return self._json(start_research_candidates(body), 202)
                if self.path == "/api/research-candidates-cancel":
                    return self._json(cancel_research_candidates(), 202)
                if self.path == "/api/research-candidates-pause":
                    return self._json(pause_research_candidates(), 202)
                if self.path == "/api/research-candidates-resume":
                    return self._json(resume_research_candidates(), 202)
                if self.path == "/api/research-package-start":
                    return self._json(start_selected_package(body), 202)
                if self.path == "/api/navigator-operation":
                    return self._json(start_navigator_operation(body), 202)
                if self.path == "/api/study-document":
                    source = Path(str(body.get("path", "") or "")).expanduser().resolve()
                    if not source.is_file():
                        raise FileNotFoundError("El archivo indicado no existe.")
                    library_root = Path(SETTINGS.library_path).expanduser().resolve()
                    source.relative_to(library_root)
                    package = application.context_builder.build_documents_package(
                        documents=[(source, source.name)],
                        objective=str(body.get("objective", "Investigación jurídica") or "Investigación jurídica"),
                        instruction=str(body.get("instruction", "") or ""),
                        document_type=str(body.get("document_type", "Detección automática") or "Detección automática"),
                    )
                    package.title = "Analisis_" + source.stem
                    saved_paths = application.context_builder.save(package)
                    return self._json({
                        "ok": True,
                        "title": str(getattr(package, "title", "Análisis del documento")),
                        "content": str(getattr(package, "content", "") or ""),
                        "saved_paths": [str(path) for path in (saved_paths or [])],
                        "same_classic_process": True,
                    })
                if self.path == "/api/import-files":
                    destination = Path(str(body.get("destination", "") or "")).resolve()
                    library_root = Path(SETTINGS.library_path).expanduser().resolve()
                    destination.relative_to(library_root)
                    if not destination.is_dir():
                        raise FileNotFoundError("La carpeta de destino ya no existe.")

                    staging_root = (_project_root() / "runtime" / "ui2_import_staging").resolve()
                    sources = body.get("sources") or []
                    if not isinstance(sources, list) or not sources:
                        raise ValueError("No se recibieron archivos para importar.")
                    if len(sources) > 100:
                        raise ValueError("Se pueden importar hasta 100 archivos por operación.")

                    allowed = {".pdf", ".doc", ".docx", ".odt", ".txt"}
                    imported, skipped, errors = [], [], []
                    for item in sources:
                        try:
                            source = Path(str(item.get("path", "") or "")).resolve()
                            source.relative_to(staging_root)
                            clean_name = Path(str(item.get("name", "") or "")).name
                            if not clean_name or Path(clean_name).suffix.lower() not in allowed:
                                raise ValueError("Nombre o extensión no admitidos.")
                            if not source.is_file():
                                raise FileNotFoundError("El archivo temporal no existe.")
                            target = (destination / clean_name).resolve()
                            target.relative_to(destination)
                            if target.exists():
                                skipped.append(str(target))
                                continue
                            temporary = destination / (
                                f".{uuid.uuid4().hex}_{clean_name}.lexia-importing"
                            )
                            try:
                                shutil.copyfile(source, temporary)
                                os.replace(temporary, target)
                            finally:
                                temporary.unlink(missing_ok=True)
                            imported.append(str(target))
                        except Exception as exc:
                            errors.append(f"{Path(str(item.get('name', '') or '')).name}: {exc}")

                    if imported:
                        application.autosync.reconcile_paths(imported)
                    return self._json({
                        "ok": True,
                        "imported": imported,
                        "skipped": skipped,
                        "errors": errors,
                        "destination": str(destination),
                        "same_classic_process": True,
                    })

                service = application.secure_document_deletion
                validated = service._validate_path(body.get("path", ""))
                confirmed_name = str(body.get("confirm_name", "") or "")
                if confirmed_name != validated.name:
                    return self._json({
                        "ok": False,
                        "error": "La confirmación no coincide con el nombre exacto del archivo.",
                    }, 403)

                if not service.start_delete(validated):
                    state = service.state()
                    return self._json({
                        "ok": False,
                        "error": (
                            "AutoSync, OCR u otra eliminación están trabajando. "
                            "Esperá a que finalicen antes de reintentar."
                        ),
                        "state": state,
                    }, 409)

                return self._json({
                    "ok": True,
                    "started": True,
                    "implementation": "SecureDocumentDeletionService",
                    "same_classic_process": True,
                    "state": service.state(),
                }, 202)
            except PermissionError as exc:
                return self._json({"ok": False, "error": str(exc)}, 403)
            except FileNotFoundError as exc:
                return self._json({"ok": False, "error": str(exc)}, 404)
            except (ValueError, RuntimeError) as exc:
                return self._json({"ok": False, "error": str(exc)}, 409)
            except Exception as exc:
                return self._json({"ok": False, "error": str(exc)}, 500)

    return DeleteBridgeHandler


def start_ui2_delete_bridge(application, port: int | None = None) -> bool:
    """Expone operaciones centrales dentro del proceso de LexIA clásica."""
    global _BRIDGE_SERVER, _BRIDGE_THREAD

    with _BRIDGE_LOCK:
        if _BRIDGE_SERVER is not None:
            return True

        selected_port = int(
            port or os.environ.get("LEXIA_DELETE_BRIDGE_PORT", "8513")
        )
        token = secrets.token_urlsafe(32)
        handler = _handler_class(application, token)

        try:
            server = ThreadingHTTPServer(("127.0.0.1", selected_port), handler)
        except OSError:
            return False

        server.daemon_threads = True
        thread = threading.Thread(
            target=server.serve_forever,
            name="LexIA-UI2-Secure-Delete-Bridge",
            daemon=True,
        )
        thread.start()
        _write_state(selected_port, token)
        _BRIDGE_SERVER = server
        _BRIDGE_THREAD = thread
        return True
