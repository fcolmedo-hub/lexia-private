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
            "document_name": str(ocr.get("document_name", "") or ""),
            "document_position": int(
                ocr.get("document_position", 0) or 0
            ),
            "processed": ocr["processed"],
            "total": ocr["total"],
            "percentage": (
                round(100 * ocr["processed"] / ocr["total"])
                if ocr["total"] else 0
            ),
            "queued": int(ocr.get("pending", 0) or 0),
            "current_page": int(ocr.get("current_page", 0) or 0),
            "total_pages": int(ocr.get("total_pages", 0) or 0),
            "page_percentage": int(ocr.get("page_percentage", 0) or 0),
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
    return Path(SETTINGS.runtime_path) / "ui2_delete_bridge.json"


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