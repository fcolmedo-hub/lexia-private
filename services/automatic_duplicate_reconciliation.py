"""Background reconciliation of stale duplicate locations; never deletes files."""
import logging
from pathlib import Path
import sqlite3
import threading
import time
from services.library_work_priority import WORK_PRIORITY

from services.moved_duplicate_reconciliation import reconcile_moved_duplicate, _finish_moves

LOGGER = logging.getLogger(__name__)


@WORK_PRIORITY.background_task('actualización de ubicaciones')
def reconcile_pass(application, progress=lambda **values: None, stop=None):
    lock = application.autosync._sync_lock
    if not lock.acquire(blocking=False):
        return {'deferred': True}
    batch = {'backup': None, 'moves': []}
    repaired, failed, processed = 0, 0, 0
    try:
        if application.ocr_queue.state().get('running'):
            return {'deferred': True}
        with sqlite3.connect(str(application.catalog.database_path), timeout=10) as db:
            rows = db.execute("SELECT path, duplicate_of FROM documents WHERE is_deleted=0 AND duplicate_of IS NOT NULL AND TRIM(duplicate_of)<>''").fetchall()
        candidates = []
        for path, original in rows:
            try:
                if Path(path).is_file() and not Path(original).exists():
                    candidates.append(path)
            except OSError:
                continue
        progress(total=len(candidates), processed=0, repaired=0, failed=0, waiting=False)
        try:
            for path in candidates:
                if WORK_PRIORITY.pending() or (stop is not None and stop.is_set()):
                    break
                progress(current_file=path)
                # A previous relocation may already have updated this reference.
                state = application.catalog.get_file_state(path)
                if not state or not state.get('duplicate_of') or Path(state['duplicate_of']).exists():
                    processed += 1
                    progress(processed=processed)
                    continue
                try:
                    result = reconcile_moved_duplicate(application, path, _batch=batch)
                    repaired += 1
                    for warning in result.get('warnings', []):
                        LOGGER.info('Reconciliación de ubicación %s: %s', path, warning)
                except (OSError, ValueError, RuntimeError, sqlite3.Error) as error:
                    failed += 1
                    LOGGER.warning('Ubicación conservada sin cambios %s: %s', path, error)
                processed += 1
                progress(processed=processed, repaired=repaired, failed=failed)
        finally:
            warnings = _finish_moves(application, batch['moves'])
        return {'deferred': WORK_PRIORITY.pending(), 'total': len(candidates), 'processed': processed,
                'repaired': repaired, 'failed': failed, 'warnings': warnings,
                'backup': str(batch['backup']) if batch['backup'] else '', 'current_file': ''}
    finally:
        lock.release()


class AutomaticDuplicateReconciler:
    def __init__(self, application):
        self.application = application
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread = None
        self._last_started = None
        self._state = {'running': False, 'total': 0, 'processed': 0, 'repaired': 0, 'failed': 0}

    def snapshot(self):
        with self._lock:
            return dict(self._state)

    def _update(self, **values):
        with self._lock:
            self._state.update(values)

    def request(self):
        with self._lock:
            if self._stop.is_set() or (self._thread and self._thread.is_alive()):
                return
            if self._last_started is not None and time.monotonic() - self._last_started < 30:
                return
            self._last_started = time.monotonic()
            self._state.update(running=True, waiting=True, error='', total=0, processed=0, repaired=0, failed=0)
            self._thread = threading.Thread(target=self._run, name='LexIA-Reconcile-Duplicate-Locations', daemon=True)
            self._thread.start()

    def _run(self):
        try:
            while not self._stop.is_set():
                result = reconcile_pass(self.application, self._update, self._stop)
                if not result.get('deferred'):
                    self._update(**result)
                    break
                self._update(waiting=True)
                if self._stop.wait(2):
                    break
        except Exception as error:
            LOGGER.exception('Falló la reconciliación automática de ubicaciones')
            self._update(error=str(error))
        finally:
            with self._lock:
                self._last_started = time.monotonic()
            self._update(running=False, waiting=False)

    def stop(self):
        self._stop.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2)
