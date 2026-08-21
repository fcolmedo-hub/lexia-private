import json
import logging
import sqlite3
import threading
import time
from time import perf_counter
from datetime import datetime
from pathlib import Path
from typing import Any

from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

from config.settings import SETTINGS
from core.pipeline import DocumentPipeline
from core.file_hasher import FileHasher
from storage.catalog import DocumentCatalog
from models.document import Document
# >>> LEXIA CLASSIFICATION TREE 1.0 FASE C IMPORT
from services.classification_shadow_sync import ClassificationShadowSync
# <<< LEXIA CLASSIFICATION TREE 1.0 FASE C IMPORT
from core.document_detector import DocumentDetector
from services.library_snapshot_service import (
    LibrarySnapshotService,
)
from storage.catalog import DocumentCatalog
from storage.search_cache_repository import (
    SearchCacheRepository,
)
from services.knowledge_engine import KnowledgeEngine


class _LibraryEventHandler(FileSystemEventHandler):
    def __init__(self, callback, move_callback):
        super().__init__()
        self.callback = callback
        self.move_callback = move_callback

    def on_created(self, event):
        if not event.is_directory:
            self.callback(
                "created",
                getattr(event, "src_path", ""),
                False,
            )

    def on_modified(self, event):
        if not event.is_directory:
            self.callback(
                "modified",
                getattr(event, "src_path", ""),
                False,
            )

    def on_closed(self, event):
        if not event.is_directory:
            self.callback(
                "closed",
                getattr(event, "src_path", ""),
                False,
            )

    def on_deleted(self, event):
        if not event.is_directory:
            self.callback(
                "deleted",
                getattr(event, "src_path", ""),
                False,
            )

    def on_moved(self, event):
        if not event.is_directory:
            self.move_callback(
                getattr(event, "src_path", ""),
                getattr(event, "dest_path", ""),
            )


class AutoSyncService:
    def __init__(self, indexer):
        self.indexer = indexer
        self.knowledge = KnowledgeEngine()
        self.catalog = DocumentCatalog(
            SETTINGS.catalog_path
        )
        self.library_snapshot = LibrarySnapshotService(
            library_path=SETTINGS.library_path,
            snapshot_path=(
                SETTINGS.runtime_path
                / "library_snapshot.json"
            ),
            supported_extensions=(
                DocumentDetector.SUPPORTED_EXTENSIONS
            ),
        )
        self.state_path = Path(
            SETTINGS.autosync_state_path
        )
        self.state_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )
        self.config_path = Path(SETTINGS.reconciliation_config_path)
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        self._config = self._load_reconciliation_config()
        self.logger = logging.getLogger(
            "lexia.autosync"
        )
        self._configure_diagnostic_logging()

        self._observer = None
        self._worker = None
        self._stop = threading.Event()
        self._changed = threading.Event()
        self._sync_lock = threading.RLock()
        self._state_lock = threading.RLock()
        self._event_lock = threading.RLock()
        self._last_change = 0.0
        self._started = False

        self._changed_files: set[str] = set()
        self._deleted_files: set[str] = set()
        self._moved_files: list[tuple[str, str]] = []
        self._full_scan_requested = False

        self._state: dict[str, Any] = {
            "status": "Listo",
            "phase": "idle",
            "current_file": "",
            "processed": 0,
            "total": 0,
            "percentage": 0,
            "documents_total": (
                self.catalog.stats()["documents"]
            ),
            "documents_indexed": 0,
            "documents_moved": 0,
            "knowledge_updated": 0,
            "knowledge_removed": 0,
            "knowledge_errors": 0,
            "last_sync": None,
            "last_error": None,
            "pending_changes": False,
            "scan_mode": "",
            "last_stage": "idle",
            "stage_timings": {},
            "snapshot_files": 0,
            "snapshot_changed": 0,
            "snapshot_deleted": 0,
            "pipeline_detected": 0,
            "pipeline_new": 0,
            "pipeline_modified": 0,
            "pipeline_skipped": 0,
            "pipeline_failed": 0,
            "pipeline_duplicates": 0,
            "pipeline_relocated": 0,
            "last_failure_stage": None,
            "last_failure_file": None,
            "last_failure_message": None,
            "sync_mode": self._config["mode"],
            "schedule_time": self._config["schedule_time"],
            "next_scheduled": "",
        }
        self._save()

    def _load_reconciliation_config(self) -> dict:
        default = {
            "mode": str(getattr(SETTINGS, "synchronization_mode", "automatic")),
            "schedule_time": str(
                getattr(SETTINGS, "reconciliation_schedule_time", "03:00")
            ),
            "last_scheduled_date": "",
        }
        if self.config_path.exists():
            try:
                loaded = json.loads(self.config_path.read_text(encoding="utf-8"))
                default.update({k: loaded[k] for k in default if k in loaded})
            except (OSError, ValueError, TypeError):
                pass
        if default["mode"] not in {"manual", "automatic", "scheduled"}:
            default["mode"] = "automatic"
        return default

    def _save_reconciliation_config(self) -> None:
        self.config_path.write_text(
            json.dumps(self._config, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def configuration(self) -> dict:
        return dict(self._config)

    def set_configuration(self, mode: str, schedule_time: str = "03:00") -> dict:
        if mode not in {"manual", "automatic", "scheduled"}:
            raise ValueError("Modo de sincronizacion no valido.")
        try:
            datetime.strptime(schedule_time, "%H:%M")
        except ValueError as error:
            raise ValueError("La hora debe tener formato HH:MM.") from error
        previous = self._config.get("mode")
        self._config["mode"] = mode
        self._config["schedule_time"] = schedule_time
        if mode != "scheduled":
            self._config["last_scheduled_date"] = ""
        self._save_reconciliation_config()
        if self._started and previous != mode:
            if mode == "automatic":
                self._start_observer()
            else:
                self._stop_observer()
        self._update(
            sync_mode=mode,
            schedule_time=schedule_time,
            status="Modo de sincronizacion actualizado",
        )
        self._changed.set()
        return self.configuration()

    def _start_observer(self) -> None:
        if self._observer is not None:
            return
        self._observer = Observer()
        self._observer.schedule(
            _LibraryEventHandler(self.notify_change, self.notify_move),
            str(SETTINGS.library_path),
            recursive=True,
        )
        self._observer.start()

    def _stop_observer(self) -> None:
        observer = self._observer
        self._observer = None
        if observer is not None:
            observer.stop()
            observer.join(timeout=5)

    def _scheduled_due(self) -> bool:
        if self._config.get("mode") != "scheduled":
            return False
        now = datetime.now()
        target = datetime.strptime(self._config["schedule_time"], "%H:%M").time()
        today = now.date().isoformat()
        if now.time() < target or self._config.get("last_scheduled_date") == today:
            return False
        try:
            with sqlite3.connect(SETTINGS.ocr_queue_path) as connection:
                busy = int(connection.execute(
                    "SELECT COUNT(*) FROM ocr_queue WHERE status = 'processing'"
                ).fetchone()[0])
            if busy:
                return False
        except sqlite3.Error:
            pass
        self._config["last_scheduled_date"] = today
        self._save_reconciliation_config()
        return True

    def _configure_diagnostic_logging(self) -> None:
        """
        Escribe el diagnóstico de AutoSync en runtime/autosync.log
        sin duplicar handlers durante reruns de Streamlit.
        """
        try:
            log_path = Path(SETTINGS.runtime_path) / "autosync.log"
            log_path.parent.mkdir(parents=True, exist_ok=True)

            for handler in self.logger.handlers:
                if getattr(handler, "_lexia_autosync_file", False):
                    return

            handler = logging.FileHandler(
                log_path,
                encoding="utf-8",
            )
            handler._lexia_autosync_file = True
            handler.setFormatter(
                logging.Formatter(
                    "%(asctime)s | %(levelname)s | %(message)s",
                    datefmt="%Y-%m-%d %H:%M:%S",
                )
            )
            self.logger.addHandler(handler)
            self.logger.setLevel(logging.INFO)
        except OSError:
            # El log nunca debe impedir que AutoSync arranque.
            pass

    def start(self) -> None:
        if (
            self._started
            or not SETTINGS.autosync_enabled
        ):
            return

        SETTINGS.library_path.mkdir(
            parents=True,
            exist_ok=True,
        )

        if self._config.get("mode") == "automatic":
            self._start_observer()

        self._stop.clear()
        self._worker = threading.Thread(
            target=self._loop,
            name="LexIA-AutoSync-3.4",
            daemon=True,
        )
        self._worker.start()
        self._started = True

        self._update(
            status="Biblioteca disponible",
            phase="idle",
            sync_mode=self._config["mode"],
            schedule_time=self._config["schedule_time"],
        )

        startup_mode = getattr(
            SETTINGS,
            "autosync_startup_mode",
            "watch_only",
        )

        if self._config.get("mode") == "automatic" and (
            SETTINGS.autosync_on_startup
            and startup_mode == "full_scan"
        ):
            self.request_full_scan(
                "startup_manual_override"
            )
        elif self._config.get("mode") == "automatic":
            self.request_full_scan(
                "startup_smart_reconcile"
            )

    def stop(self) -> None:
        self._stop.set()
        self._changed.set()

        self._stop_observer()

        if self._worker:
            self._worker.join(timeout=5)

        self._started = False

    def notify_change(
        self,
        event_type: str,
        event_path: str,
        is_directory: bool,
    ) -> None:
        if not event_path or is_directory:
            return

        resolved = str(Path(event_path).resolve())

        with self._event_lock:
            if event_type == "deleted":
                self._deleted_files.add(resolved)
                self._changed_files.discard(resolved)
            else:
                self._changed_files.add(resolved)
                self._deleted_files.discard(resolved)

        self._last_change = time.monotonic()
        self._changed.set()

        self._update(
            status="Cambio detectado",
            phase="waiting",
            current_file=Path(resolved).name,
            pending_changes=True,
            scan_mode="targeted",
        )

    def notify_move(
        self,
        source_path: str,
        destination_path: str,
    ) -> None:
        # >>> LEXIA AUTOSYNC STABLE SAVE 2.0
        # Un evento MOVED de Watchdog no prueba una relocalización real.
        # Word/LibreOffice pueden guardar mediante renombres temporales.
        # Por seguridad, todo MOVED se resuelve con Smart Snapshot después
        # del debounce, usando el estado físico final como fuente de verdad.
        if not source_path and not destination_path:
            return

        visible_path = destination_path or source_path

        with self._event_lock:
            self._full_scan_requested = True

            # >>> LEXIA MOVE FAST PATH 1.0 — PRESERVE MOVES
            # Conserva old_path -> new_path. El full scan se mantiene
            # como red de seguridad para guardados atomicos.
            if source_path and destination_path:
                try:
                    move_pair = (
                        str(Path(source_path).resolve()),
                        str(Path(destination_path).resolve()),
                    )
                except OSError:
                    move_pair = (str(source_path), str(destination_path))
                if move_pair[0] != move_pair[1]:
                    self._moved_files.append(move_pair)
            # <<< LEXIA MOVE FAST PATH 1.0 — PRESERVE MOVES

        self._last_change = time.monotonic()
        self._changed.set()

        self._update(
            status="Movimiento detectado; verificando estado final",
            phase="waiting",
            current_file=Path(visible_path).name,
            pending_changes=True,
            scan_mode="smart_reconcile",
        )
        # <<< LEXIA AUTOSYNC STABLE SAVE 2.0

    def request_full_scan(self, reason: str = "manual"):
        with self._event_lock:
            self._full_scan_requested = True

        self._last_change = time.monotonic()
        self._changed.set()
        self._update(
            status="🔍 Buscando cambios...",
            phase="waiting",
            scan_mode=reason,
            pending_changes=True,
        )

    def sync_now(self) -> dict:
        self.request_full_scan("manual_reconcile")
        return {
            "status": (
                "La búsqueda manual de cambios pendientes fue puesta en cola."
            )
        }

    def reconcile_paths(self, paths) -> None:
        resolved = {
            str(Path(path).resolve())
            for path in (paths or [])
            if path
        }
        if not resolved:
            return
        with self._event_lock:
            self._changed_files.update(resolved)
            self._deleted_files.difference_update(resolved)
        self._last_change = time.monotonic()
        self._changed.set()
        self._update(
            status="Procesamiento dirigido en cola",
            phase="waiting",
            pending_changes=True,
            scan_mode="directed_import",
        )

    def preview_reconciliation(self) -> dict:
        changed, deleted, current = self.library_snapshot.scan()
        previous = self.library_snapshot.load()
        new_paths = sorted(path for path in changed if path not in previous)
        modified_paths = sorted(path for path in changed if path in previous)
        pending_vectors = self.catalog.pending_vector_document_count()
        pending_vector_relocations = (
            self.catalog.pending_vector_relocation_count()
        )
        physical_changes = len(changed) + len(deleted)
        return {
            "new": new_paths,
            "modified": modified_paths,
            "deleted": sorted(deleted),
            "current_total": len(current),
            "total_changes": physical_changes,
            "pending_vectors": pending_vectors,
            "pending_vector_relocations": pending_vector_relocations,
            "total_work": (
                physical_changes
                + pending_vectors
                + pending_vector_relocations
            ),
        }

    def request_stop_indexing(self) -> bool:
        if self.state().get("phase") != "indexing":
            return False
        self.indexer.request_stop()
        self._update(status="Deteniendo indexacion al finalizar el lote actual")
        return True

    def state(self) -> dict:
        with self._state_lock:
            return dict(self._state)

    def _take_work(self):
        with self._event_lock:
            full_scan = self._full_scan_requested
            changed = set(self._changed_files)
            deleted = set(self._deleted_files)
            moved = list(self._moved_files)

            self._full_scan_requested = False
            self._changed_files.clear()
            self._deleted_files.clear()
            self._moved_files.clear()

        # >>> LEXIA AUTOSYNC SAFE SAVE FIX 1.0
        # Algunos editores guardan reemplazando temporalmente el archivo.
        # Tras el debounce, la fuente de verdad es el estado físico FINAL.
        all_event_paths = set(changed) | set(deleted)
        for event_path in all_event_paths:
            try:
                exists_now = Path(event_path).exists()
            except OSError:
                exists_now = False

            if exists_now:
                deleted.discard(event_path)
                changed.add(event_path)
            else:
                changed.discard(event_path)
                deleted.add(event_path)
        # <<< LEXIA AUTOSYNC SAFE SAVE FIX 1.0

        # >>> LEXIA MOVE FAST PATH 1.0 — VALIDATE MOVES
        # Solo acepta como MOVE real: origen ausente + destino existente.
        validated_moved: list[tuple[str, str]] = []
        seen_moves: set[tuple[str, str]] = set()
        for old_path, new_path in moved:
            try:
                old_resolved = str(Path(old_path).resolve())
                new_resolved = str(Path(new_path).resolve())
                old_exists = Path(old_resolved).exists()
                new_exists = Path(new_resolved).exists()
            except OSError:
                continue
            pair = (old_resolved, new_resolved)
            if (
                old_resolved != new_resolved
                and not old_exists
                and new_exists
                and pair not in seen_moves
            ):
                validated_moved.append(pair)
                seen_moves.add(pair)
        moved = validated_moved
        # <<< LEXIA MOVE FAST PATH 1.0 — VALIDATE MOVES

        return full_scan, changed, deleted, moved

    def _execute(
        self,
        full_scan: bool,
        changed: set[str],
        deleted: set[str],
        moved: list[tuple[str, str]] | None = None,
    ) -> None:
        with self._sync_lock:
            mode = "🔍 Buscando cambios..."

            self._update(
                status=mode,
                phase="scanning",
                processed=0,
                total=0,
                percentage=0,
                current_file="",
                scan_mode=(
                    "full" if full_scan else "targeted"
                ),
                pending_changes=False,
                last_error=None,
            )

            started_at = perf_counter()
            stage = "reconciliation"
            stage_timings: dict[str, float] = {}

            try:
                self.logger.info(
                    "Sincronización iniciada | mode=%s | full_scan=%s | "
                    "changed=%s | deleted=%s | moved=%s",
                    mode,
                    full_scan,
                    len(changed),
                    len(deleted),
                    len(moved or []),
                )

                snapshot_after_scan = None
                moved = moved or []
                move_successes: list[tuple[str, str]] = []
                move_failures: list[tuple[str, str]] = []

                reconciliation_started = perf_counter()

                for old_path, new_path in moved:
                    try:
                        moved_in_knowledge = self.knowledge.move_document(
                            old_path,
                            new_path,
                        )
                        if moved_in_knowledge:
                            move_successes.append((old_path, new_path))
                        else:
                            move_failures.append((old_path, new_path))
                    except Exception:
                        self.logger.exception(
                            "No se pudo relocalizar Knowledge: %s -> %s",
                            old_path,
                            new_path,
                        )
                        move_failures.append((old_path, new_path))

                for old_path, new_path in move_failures:
                    deleted.add(old_path)
                    changed.add(new_path)

                # >>> LEXIA AUTOSYNC SAFE SAVE FIX 1.1
                # Segunda reconciliación: move_failures puede volver a agregar
                # rutas a deleted DESPUÉS de _take_work(). En guardados atómicos
                # de Word/LibreOffice esos movimientos pueden ser transitorios.
                # Antes del snapshot/pipeline, manda el estado físico FINAL.
                post_move_paths = set(changed) | set(deleted)
                for event_path in post_move_paths:
                    try:
                        exists_now = Path(event_path).exists()
                    except OSError:
                        exists_now = False

                    if exists_now:
                        deleted.discard(event_path)
                        changed.add(event_path)
                    else:
                        changed.discard(event_path)
                        deleted.add(event_path)
                # <<< LEXIA AUTOSYNC SAFE SAVE FIX 1.1

                stage_timings["move_reconciliation"] = round(
                    perf_counter() - reconciliation_started,
                    3,
                )

                if full_scan:
                    stage = "smart_snapshot"
                    self._update(
                        last_stage=stage,
                        stage_timings=dict(stage_timings),
                    )
                    snapshot_started = perf_counter()

                    (
                        smart_changed,
                        smart_deleted,
                        snapshot_after_scan,
                    ) = self.library_snapshot.scan()

                    stage_timings["smart_snapshot"] = round(
                        perf_counter() - snapshot_started,
                        3,
                    )

                    try:
                        snapshot_files = len(snapshot_after_scan or {})
                    except TypeError:
                        snapshot_files = 0

                    self._update(
                        snapshot_files=snapshot_files,
                        snapshot_changed=len(smart_changed),
                        snapshot_deleted=len(smart_deleted),
                        stage_timings=dict(stage_timings),
                    )
                    self.logger.info(
                        "Smart Snapshot finalizado | files=%s | "
                        "changed=%s | deleted=%s | %.3fs",
                        snapshot_files,
                        len(smart_changed),
                        len(smart_deleted),
                        stage_timings["smart_snapshot"],
                    )

                    if self.library_snapshot.initialized():
                        # >>> LEXIA STARTUP RELOCATION ECHO SUPPRESSION 1.0.1
                        # Debe ejecutarse AQUI: smart_changed/smart_deleted ya
                        # provienen del full scan y full_scan aun no fue puesto
                        # en False.
                        if smart_changed and smart_deleted:
                            try:
                                startup_echo = self.catalog.find_startup_relocation_echoes(
                                    smart_changed,
                                    smart_deleted,
                                )
                            except Exception:
                                startup_echo = {
                                    "changed": set(),
                                    "deleted": set(),
                                }
                                self.logger.exception(
                                    "Startup Relocation Echo Suppression 1.0.1 fallo"
                                )

                            startup_echo_changed = set(
                                startup_echo.get("changed") or []
                            )
                            startup_echo_deleted = set(
                                startup_echo.get("deleted") or []
                            )

                            if startup_echo_changed or startup_echo_deleted:
                                smart_changed -= startup_echo_changed
                                smart_deleted -= startup_echo_deleted
                                self.logger.info(
                                    "Startup Relocation Echo Suppression 1.0.1 | "
                                    "changed_suppressed=%s | deleted_suppressed=%s | "
                                    "remaining_changed=%s | remaining_deleted=%s",
                                    len(startup_echo_changed),
                                    len(startup_echo_deleted),
                                    len(smart_changed),
                                    len(smart_deleted),
                                )
                        # <<< LEXIA STARTUP RELOCATION ECHO SUPPRESSION 1.0.1

                        changed = smart_changed
                        deleted = smart_deleted
                        full_scan = False

                else:
                    self._update(
                        snapshot_files=0,
                        snapshot_changed=len(changed),
                        snapshot_deleted=len(deleted),
                    )

                # >>> LEXIA RESIDUAL MOVE EVENTS SUPPRESSION 1.0.1
                if not hasattr(self, "_recent_relocation_paths"):
                    self._recent_relocation_paths = set()

                residual_candidates = {
                    str(Path(path).resolve())
                    for path in changed
                } & self._recent_relocation_paths

                if residual_candidates:
                    changed -= residual_candidates
                    self._recent_relocation_paths -= residual_candidates
                    self.logger.info(
                        "Residual Move Events Suppression 1.0.1 | "
                        "suppressed=%s | remaining_changed=%s",
                        len(residual_candidates),
                        len(changed),
                    )
                # <<< LEXIA RESIDUAL MOVE EVENTS SUPPRESSION 1.0.1

                # >>> LEXIA SMART RELOCATION 1.1
                # Fast path comun a sincronizaciones FULL y TARGETED.
                smart_relocations: list[tuple[str, str]] = []
                smart_batch_documents: list[tuple[str, Document]] = []
                smart_relocation_new_paths: set[str] = set()
                # >>> LEXIA SMART RELOCATION BATCH INTEGRATION 1.0.2
                # Relocalizacion de catalogo en una unica transaccion por lote.
                # <<< LEXIA SMART RELOCATION BATCH INTEGRATION 1.0.2
                smart_diag = {
                    "changed": len(changed),
                    "deleted": len(deleted),
                    "old_states": 0,
                    "old_hashes": 0,
                    "new_hashes": 0,
                    "matched": 0,
                    "ambiguous": 0,
                    "unmatched": 0,
                    "hash_errors": 0,
                    "relocate_failures": 0,
                }

                # >>> LEXIA SMART RELOCATION TIMING PROBE 1.0
                smart_probe_started = perf_counter()
                smart_probe_old_state = 0.0
                smart_probe_hashing = 0.0
                smart_probe_catalog = 0.0
                smart_probe_knowledge = 0.0
                # <<< LEXIA SMART RELOCATION TIMING PROBE 1.0

                if changed and deleted:
                    try:
                        catalog = DocumentCatalog(SETTINGS.catalog_path)
                        hasher = FileHasher()

                        deleted_by_hash: dict[str, list[str]] = {}
                        old_state_by_path: dict[str, dict] = {}

                        for old_path in list(deleted):
                            _probe_t0 = perf_counter()
                            try:
                                state = catalog.get_file_state(old_path)
                            except Exception:
                                state = None
                            finally:
                                smart_probe_old_state += (
                                    perf_counter() - _probe_t0
                                )

                            if not state:
                                continue

                            smart_diag["old_states"] += 1
                            old_state_by_path[old_path] = state
                            old_hash = str(
                                state.get("content_hash") or ""
                            ).strip()
                            if old_hash:
                                smart_diag["old_hashes"] += 1
                                deleted_by_hash.setdefault(
                                    old_hash, []
                                ).append(old_path)

                        matched_old: set[str] = set()
                        matched_new: set[str] = set()

                        # >>> LEXIA SMART RELOCATION FAST FINGERPRINT 1.0
                        # Para un movimiento puro en el mismo filesystem,
                        # nombre + tamaño + modified_ns permanecen invariantes.
                        # Si el candidato es único, reutilizamos el content_hash
                        # ya conocido y evitamos releer el PDF completo.
                        deleted_by_fast_fingerprint: dict[
                            tuple[str, int, int],
                            list[str],
                        ] = {}

                        for _old_path, _state in old_state_by_path.items():
                            try:
                                _fp = (
                                    Path(_old_path).name,
                                    int(_state.get("size") or -1),
                                    int(_state.get("modified_ns") or -1),
                                )
                            except Exception:
                                continue

                            deleted_by_fast_fingerprint.setdefault(
                                _fp,
                                [],
                            ).append(_old_path)

                        fast_fingerprint_matches = 0
                        fast_fingerprint_fallback_hashes = 0
                        # <<< LEXIA SMART RELOCATION FAST FINGERPRINT 1.0

                        for new_path in list(changed):
                            new_file = Path(new_path)

                            try:
                                if not new_file.exists() or not new_file.is_file():
                                    smart_diag["unmatched"] += 1
                                    continue
                            except OSError:
                                smart_diag["unmatched"] += 1
                                continue

                            # >>> LEXIA SMART RELOCATION FAST FINGERPRINT 1.0
                            try:
                                stat = new_file.stat()
                            except OSError:
                                smart_diag["unmatched"] += 1
                                continue

                            fast_fp = (
                                new_file.name,
                                int(stat.st_size),
                                int(stat.st_mtime_ns),
                            )
                            fast_candidates = [
                                old_path
                                for old_path in deleted_by_fast_fingerprint.get(
                                    fast_fp,
                                    [],
                                )
                                if old_path not in matched_old
                                and not Path(old_path).exists()
                            ]

                            if len(fast_candidates) == 1:
                                old_path = fast_candidates[0]
                                state = old_state_by_path.get(old_path)
                                if not state:
                                    smart_diag["unmatched"] += 1
                                    continue

                                new_hash = str(
                                    state.get("content_hash") or ""
                                ).strip()
                                if not new_hash:
                                    fast_candidates = []

                            if len(fast_candidates) == 1:
                                candidates = fast_candidates
                                fast_fingerprint_matches += 1
                            else:
                                fast_fingerprint_fallback_hashes += 1

                                _probe_t0 = perf_counter()
                                try:
                                    new_hash = hasher.calculate(new_file)
                                    smart_diag["new_hashes"] += 1
                                except Exception:
                                    smart_diag["hash_errors"] += 1
                                    self.logger.exception(
                                        "Smart Relocation 1.1: hash fallo: %s",
                                        new_path,
                                    )
                                    continue
                                finally:
                                    smart_probe_hashing += (
                                        perf_counter() - _probe_t0
                                    )

                                candidates = [
                                    old_path
                                    for old_path in deleted_by_hash.get(
                                        new_hash, []
                                    )
                                    if old_path not in matched_old
                                    and not Path(old_path).exists()
                                ]

                                if len(candidates) > 1:
                                    same_name = [
                                        old_path
                                        for old_path in candidates
                                        if Path(old_path).name == new_file.name
                                    ]
                                    if len(same_name) == 1:
                                        candidates = same_name

                            if len(candidates) != 1:
                                if candidates:
                                    smart_diag["ambiguous"] += 1
                                else:
                                    smart_diag["unmatched"] += 1
                                continue

                            old_path = candidates[0]
                            state = old_state_by_path.get(old_path)
                            if not state:
                                smart_diag["unmatched"] += 1
                                continue
                            # <<< LEXIA SMART RELOCATION FAST FINGERPRINT 1.0

                            try:
                                document = Document(
                                    name=new_file.name,
                                    path=new_file,
                                    category=str(
                                        state.get("category")
                                        or "Sin categoria"
                                    ),
                                    extension=new_file.suffix.lower(),
                                    size=int(stat.st_size),
                                    modified_ns=int(stat.st_mtime_ns),
                                    content_hash=new_hash,
                                    text=str(
                                        state.get("text_content") or ""
                                    ),
                                    extraction_error=(
                                        state.get("extraction_error")
                                    ),
                                    metadata={},
                                    extraction_method=str(
                                        state.get("extraction_method")
                                        or "native"
                                    ),
                                    ocr_pages=0,
                                    total_pages=None,
                                    duplicate_of=state.get("duplicate_of"),
                                )

                            except Exception:
                                relocated = False
                                self.logger.exception(
                                    "Smart Relocation 1.1 fallo: %s -> %s",
                                    old_path,
                                    new_path,
                                )

                            smart_relocations.append((old_path, new_path))
                            smart_batch_documents.append((old_path, document))
                            matched_old.add(old_path)
                            matched_new.add(new_path)
                            smart_relocation_new_paths.add(
                                str(new_file.resolve())
                            )

                        # >>> LEXIA SMART RELOCATION FAST FINGERPRINT 1.0
                        if fast_fingerprint_matches or fast_fingerprint_fallback_hashes:
                            self.logger.info(
                                "Smart Relocation Fast Fingerprint 1.0 | "
                                "fast_matches=%s | full_hash_fallbacks=%s",
                                fast_fingerprint_matches,
                                fast_fingerprint_fallback_hashes,
                            )
                        # <<< LEXIA SMART RELOCATION FAST FINGERPRINT 1.0

                        if smart_relocations:
                            batch_ok = False
                            try:
                                _probe_t0 = perf_counter()
                                batch_result = catalog.relocate_documents_batch(
                                    smart_batch_documents
                                )
                                batch_elapsed = perf_counter() - _probe_t0
                                smart_probe_catalog += batch_elapsed
                                batch_ok = (
                                    int(batch_result.get("relocated", 0))
                                    == len(smart_batch_documents)
                                    and not (batch_result.get("failed") or [])
                                )
                                self.logger.info(
                                    "Smart Relocation Batch Integration 1.0.2 | "
                                    "requested=%s | relocated=%s | failed=%s | %.3fs",
                                    len(smart_batch_documents),
                                    int(batch_result.get("relocated", 0)),
                                    len(batch_result.get("failed") or []),
                                    batch_elapsed,
                                )
                            except Exception:
                                self.logger.exception(
                                    "Smart Relocation Batch Integration 1.0.2 fallo"
                                )
                                batch_ok = False

                            if batch_ok:
                                changed -= matched_new
                                deleted -= matched_old
                                move_successes.extend(smart_relocations)

                                # >>> LEXIA RESIDUAL MOVE EVENTS SUPPRESSION 1.0.1
                                if not hasattr(self, "_recent_relocation_paths"):
                                    self._recent_relocation_paths = set()
                                self._recent_relocation_paths.update(
                                    str(Path(path).resolve())
                                    for path in matched_new
                                )
                                # <<< LEXIA RESIDUAL MOVE EVENTS SUPPRESSION 1.0.1

                                # >>> LEXIA KNOWLEDGE RELOCATION BATCH INTEGRATION 1.0.1
                                try:
                                    _probe_t0 = perf_counter()
                                    knowledge_batch = self.knowledge.move_documents(
                                        smart_relocations
                                    )
                                    knowledge_batch_elapsed = perf_counter() - _probe_t0
                                    smart_probe_knowledge += knowledge_batch_elapsed
                                    self.logger.info(
                                        "Knowledge Relocation Batch 1.0.1 | "
                                        "requested=%s | moved=%s | missing=%s | %.3fs",
                                        int(knowledge_batch.get("requested", 0)),
                                        int(knowledge_batch.get("moved", 0)),
                                        int(knowledge_batch.get("missing", 0)),
                                        knowledge_batch_elapsed,
                                    )
                                except Exception:
                                    self.logger.exception(
                                        "Knowledge Relocation Batch 1.0.1 fallo"
                                    )
                                # <<< LEXIA KNOWLEDGE RELOCATION BATCH INTEGRATION 1.0.1
                            else:
                                # Batch incompleto: mantener changed/deleted para Pipeline.
                                smart_diag["relocate_failures"] += len(smart_relocations)
                                smart_relocations = []
                                smart_batch_documents = []
                                matched_old.clear()
                                matched_new.clear()
                                smart_relocation_new_paths.clear()

                        smart_diag["matched"] = len(smart_relocations)

                    except Exception:
                        self.logger.exception(
                            "Smart Relocation 1.1 fallo global; "
                            "se continua por Pipeline normal"
                        )

                self.logger.info(
                    "Smart Relocation 1.1 | changed=%s | deleted=%s | "
                    "old_states=%s | old_hashes=%s | new_hashes=%s | "
                    "matched=%s | ambiguous=%s | unmatched=%s | "
                    "hash_errors=%s | relocate_failures=%s | "
                    "remaining_changed=%s | remaining_deleted=%s",
                    smart_diag["changed"],
                    smart_diag["deleted"],
                    smart_diag["old_states"],
                    smart_diag["old_hashes"],
                    smart_diag["new_hashes"],
                    smart_diag["matched"],
                    smart_diag["ambiguous"],
                    smart_diag["unmatched"],
                    smart_diag["hash_errors"],
                    smart_diag["relocate_failures"],
                    len(changed),
                    len(deleted),
                )
                smart_probe_total = perf_counter() - smart_probe_started
                smart_probe_other = max(
                    0.0,
                    smart_probe_total
                    - smart_probe_old_state
                    - smart_probe_hashing
                    - smart_probe_catalog
                    - smart_probe_knowledge,
                )
                self.logger.info(
                    "Smart Relocation Timing Probe 1.0 | "
                    "old_state=%.3fs | hashing=%.3fs | "
                    "catalog=%.3fs | knowledge=%.3fs | "
                    "other=%.3fs | total=%.3fs",
                    smart_probe_old_state,
                    smart_probe_hashing,
                    smart_probe_catalog,
                    smart_probe_knowledge,
                    smart_probe_other,
                    smart_probe_total,
                )
                # <<< LEXIA SMART RELOCATION 1.1

                def pipeline_progress(
                    done: int,
                    total: int,
                    path: str,
                ):
                    percentage = (
                        50
                        if total <= 0
                        else min(
                            50,
                            int(done / total * 50),
                        )
                    )
                    self._update(
                        status=mode,
                        phase="scanning",
                        current_file=("" if path == "Completado" else str(path)),
                        processed=done,
                        total=total,
                        percentage=percentage,
                    )

                stage = "pipeline"
                self._update(
                    last_stage=stage,
                    last_failure_stage=None,
                    last_failure_file=None,
                    last_failure_message=None,
                )
                pipeline_started = perf_counter()

                pipeline = DocumentPipeline().run(
                    progress_callback=pipeline_progress,
                    changed_paths=(
                        None if full_scan else changed
                    ),
                    full_scan=full_scan,
                    deleted_paths=deleted,
                )

                stage_timings["pipeline"] = round(
                    perf_counter() - pipeline_started,
                    3,
                )
                self._update(
                    pipeline_detected=int(
                        getattr(pipeline, "detected", 0) or 0
                    ),
                    pipeline_new=int(
                        getattr(pipeline, "new", 0) or 0
                    ),
                    pipeline_modified=int(
                        getattr(pipeline, "modified", 0) or 0
                    ),
                    pipeline_skipped=int(
                        getattr(pipeline, "skipped", 0) or 0
                    ),
                    pipeline_failed=int(
                        getattr(pipeline, "failed", 0) or 0
                    ),
                    pipeline_duplicates=int(
                        getattr(pipeline, "duplicates", 0) or 0
                    ),
                    pipeline_relocated=int(
                        getattr(pipeline, "relocated", 0) or 0
                    ),
                    stage_timings=dict(stage_timings),
                )
                self.logger.info(
                    "Pipeline finalizado | detected=%s | new=%s | "
                    "modified=%s | skipped=%s | failed=%s | %.3fs",
                    getattr(pipeline, "detected", 0),
                    getattr(pipeline, "new", 0),
                    getattr(pipeline, "modified", 0),
                    getattr(pipeline, "skipped", 0),
                    getattr(pipeline, "failed", 0),
                    stage_timings["pipeline"],
                )

                stage = "snapshot_persistence"
                snapshot_persist_started = perf_counter()

                # >>> LEXIA CLASSIFICATION TREE 1.0 FASE C AUTOSYNC
                # Mantener SOLO shadow metadata para rutas físicamente
                # procesadas por este ciclo. No toca category legacy ni
                # contenido/indexación.
                shadow_paths = set(changed)
                shadow_paths.update(smart_relocation_new_paths)
                try:
                    shadow_paths.update(
                        str(Path(item).resolve())
                        for item in getattr(pipeline, "relocated_paths", []) or []
                    )
                except Exception:
                    pass
                shadow_probe_started = perf_counter()
                try:
                    shadow_sync = ClassificationShadowSync(
                        Path(__file__).resolve().parents[1]
                    )
                    shadow_result = shadow_sync.update_paths(shadow_paths)
                    self.logger.info(
                        "Classification shadow sync | requested=%s | "
                        "updated=%s | missing=%s | invalid=%s",
                        shadow_result.get("requested", 0),
                        shadow_result.get("updated", 0),
                        shadow_result.get("missing", 0),
                        shadow_result.get("invalid", 0),
                    )
                except Exception:
                    self.logger.exception(
                        "Classification shadow sync falló"
                    )
                shadow_probe_elapsed = (
                    perf_counter() - shadow_probe_started
                )
                self.logger.info(
                    "Timing Probe 1.0 | classification_shadow=%.3fs",
                    shadow_probe_elapsed,
                )
                # <<< LEXIA CLASSIFICATION TREE 1.0 FASE C AUTOSYNC

                snapshot_write_started = perf_counter()
                if snapshot_after_scan is not None:
                    self.library_snapshot.save(
                        snapshot_after_scan
                    )
                else:
                    self.library_snapshot.apply_changes(
                        changed_paths=set(changed),
                        deleted_paths=(
                            set(deleted)
                            | set(pipeline.deleted_paths)
                        ),
                    )

                snapshot_write_elapsed = (
                    perf_counter() - snapshot_write_started
                )
                self.logger.info(
                    "Timing Probe 1.0 | snapshot_write=%.3fs",
                    snapshot_write_elapsed,
                )

                stage_timings["snapshot_persistence"] = round(
                    perf_counter() - snapshot_persist_started,
                    3,
                )
                self._update(
                    stage_timings=dict(stage_timings),
                )
                self.logger.info(
                    "Snapshot persistido | %.3fs",
                    stage_timings["snapshot_persistence"],
                )

                def index_progress(
                    done: int,
                    total: int,
                    path: str,
                ):
                    percentage = 50 + (
                        49
                        if total <= 0
                        else min(
                            49,
                            int(done / total * 49),
                        )
                    )
                    self._update(
                        status="⚙️ Procesando documentos...",
                        phase="indexing",
                        current_file=("" if path == "Completado" else str(path)),
                        processed=done,
                        total=total,
                        percentage=percentage,
                    )

                stage = "vector_indexing"
                self._update(
                    last_stage=stage,
                    stage_timings=dict(stage_timings),
                )
                index_started = perf_counter()

                indexed = self.indexer.run(
                    pipeline.deleted_paths,
                    progress_callback=index_progress,
                )

                stage_timings["vector_indexing"] = round(
                    perf_counter() - index_started,
                    3,
                )
                self._update(
                    stage_timings=dict(stage_timings),
                )
                self.logger.info(
                    "Indexación vectorial finalizada | indexed=%s | "
                    "relocated=%s | %.3fs",
                    getattr(indexed, "documents_indexed", 0),
                    getattr(indexed, "documents_relocated", 0),
                    stage_timings["vector_indexing"],
                )

                affected_paths = set(changed)
                removed_paths = set(deleted)
                moved_paths = {
                    new_path
                    for _, new_path in move_successes
                }
                affected_paths -= moved_paths
                removed_paths.update(
                    pipeline.deleted_paths
                )

                def knowledge_progress(
                    done: int,
                    total: int,
                    path: str,
                ):
                    percentage = 99 if total <= 0 else min(
                        99,
                        90 + int(done / total * 9),
                    )
                    self._update(
                        status="Actualizando Knowledge Engine",
                        phase="knowledge",
                        current_file=("" if path == "Completado" else str(path)),
                        processed=done,
                        total=total,
                        percentage=percentage,
                    )

                stage = "knowledge"
                self._update(
                    last_stage=stage,
                    stage_timings=dict(stage_timings),
                )
                knowledge_started = perf_counter()

                # >>> LEXIA KNOWLEDGE RELOCATION SKIP 1.0
                knowledge_sync_paths = {
                    str(Path(path).resolve())
                    for path in affected_paths
                }
                knowledge_sync_paths -= {
                    str(Path(path).resolve())
                    for path in smart_relocation_new_paths
                }

                knowledge_result = self.knowledge.sync_paths(
                    knowledge_sync_paths,
                    deleted_paths=removed_paths,
                    rebuild_relations=False,
                    progress_callback=knowledge_progress,
                )

                if smart_relocation_new_paths:
                    self.logger.info(
                        "Knowledge Relocation Skip 1.0 | "
                        "relocated_excluded=%s | sync_requested=%s",
                        len(smart_relocation_new_paths),
                        len(knowledge_sync_paths),
                    )
                # <<< LEXIA KNOWLEDGE RELOCATION SKIP 1.0

                stage_timings["knowledge"] = round(
                    perf_counter() - knowledge_started,
                    3,
                )
                self._update(
                    stage_timings=dict(stage_timings),
                )
                self.logger.info(
                    "Knowledge finalizado | updated=%s | removed=%s | "
                    "errors=%s | %.3fs",
                    getattr(knowledge_result, "updated", 0),
                    getattr(knowledge_result, "removed", 0),
                    getattr(knowledge_result, "errors", 0),
                    stage_timings["knowledge"],
                )

                stage = "finalization"
                finalization_started = perf_counter()

                SearchCacheRepository(
                    SETTINGS.search_cache_path
                ).clear()

                total_documents = (
                    self.catalog.stats()["documents"]
                )

                stage_timings["finalization"] = round(
                    perf_counter() - finalization_started,
                    3,
                )

                stage_timings["total"] = round(
                    perf_counter() - started_at,
                    3,
                )
                measured = sum(
                    value
                    for key, value in stage_timings.items()
                    if key != "total"
                )
                stage_timings["unaccounted"] = round(
                    max(0.0, stage_timings["total"] - measured),
                    3,
                )
                self.logger.info(
                    "Sincronización completada | "
                    "move=%.3fs | snapshot=%.3fs | pipeline=%.3fs | "
                    "snapshot_persist=%.3fs | vector=%.3fs | "
                    "knowledge=%.3fs | finalization=%.3fs | "
                    "unaccounted=%.3fs | total=%.3fs",
                    stage_timings.get("move_reconciliation", 0.0),
                    stage_timings.get("smart_snapshot", 0.0),
                    stage_timings.get("pipeline", 0.0),
                    stage_timings.get("snapshot_persistence", 0.0),
                    stage_timings.get("vector_indexing", 0.0),
                    stage_timings.get("knowledge", 0.0),
                    stage_timings.get("finalization", 0.0),
                    stage_timings.get("unaccounted", 0.0),
                    stage_timings["total"],
                )

                self._update(
                    status=(
                        "Indexacion detenida; quedan vectores pendientes"
                        if getattr(indexed, "cancelled", False)
                        else "Biblioteca al día"
                    ),
                    phase="completed",
                    current_file="",
                    last_stage="completed",
                    stage_timings=dict(stage_timings),
                    last_failure_stage=None,
                    last_failure_file=None,
                    last_failure_message=None,
                    processed=(
                        indexed.documents_indexed
                    ),
                    total=(
                        indexed.documents_indexed
                    ),
                    percentage=100,
                    documents_total=total_documents,
                    documents_indexed=(
                        indexed.documents_indexed
                    ),
                    documents_moved=(
                        indexed.documents_relocated
                        + len(move_successes)
                    ),
                    knowledge_updated=(
                        knowledge_result.updated
                    ),
                    knowledge_removed=(
                        knowledge_result.removed
                    ),
                    knowledge_errors=(
                        knowledge_result.errors
                    ),
                    last_sync=datetime.now().isoformat(
                        timespec="seconds"
                    ),
                    pending_changes=bool(
                        getattr(indexed, "cancelled", False)
                    ),
                )

            except Exception as error:
                failed_file = ""
                try:
                    failed_file = str(
                        self.state().get("current_file", "") or ""
                    )
                except Exception:
                    failed_file = ""

                stage_timings["total"] = round(
                    perf_counter() - started_at,
                    3,
                )
                self.logger.exception(
                    "AutoSync 3.4 | stage=%s | file=%s | elapsed=%.3fs",
                    stage,
                    failed_file,
                    stage_timings["total"],
                )
                self._update(
                    status="Error de sincronización",
                    phase="error",
                    current_file=failed_file,
                    last_stage=stage,
                    last_error=str(error),
                    last_failure_stage=stage,
                    last_failure_file=failed_file or None,
                    last_failure_message=str(error),
                    stage_timings=dict(stage_timings),
                    pending_changes=True,
                )

    def _loop(self) -> None:
        while not self._stop.is_set():
            interval = int(
                getattr(
                    SETTINGS,
                    "autosync_scan_interval_seconds",
                    0,
                )
                or 0
            )
            mode = self._config.get("mode", "automatic")
            timeout = 30 if mode == "scheduled" else (
                None if interval <= 0 else interval
            )
            triggered = self._changed.wait(timeout=timeout)

            if self._stop.is_set():
                break

            if not triggered and self._scheduled_due():
                self.request_full_scan("scheduled_reconcile")
                continue

            if not triggered:
                continue

            while not self._stop.is_set():
                remaining = (
                    SETTINGS.autosync_debounce_seconds
                    - (
                        time.monotonic()
                        - self._last_change
                    )
                )
                if remaining <= 0:
                    break
                time.sleep(min(remaining, 0.4))

            if self._stop.is_set():
                break

            self._changed.clear()
            full_scan, changed, deleted, moved = (
                self._take_work()
            )

            if full_scan or changed or deleted or moved:
                self._execute(
                    full_scan,
                    changed,
                    deleted,
                    moved,
                )

    def _update(self, **changes) -> None:
        with self._state_lock:
            self._state.update(changes)
        self._save()

    def _save(self) -> None:
        try:
            with self._state_lock:
                payload = dict(self._state)

            self.state_path.write_text(
                json.dumps(
                    payload,
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
        except OSError:
            self.logger.exception(
                "No se pudo guardar AutoSync."
            )
