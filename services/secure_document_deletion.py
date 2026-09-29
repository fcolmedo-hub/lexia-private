from __future__ import annotations

import errno
import os
import json
import sqlite3
import shutil
import sys
import threading
import time
import uuid
from pathlib import Path

from qdrant_client import models

from config.settings import SETTINGS
from services.duplicate_file_safety import require_identical_files
from services.library_work_priority import WORK_PRIORITY


class SecureDocumentDeletionService:
    """Elimina un documento y todos sus derivados activos en LexIA."""

    def __init__(
        self,
        catalog,
        vector_store,
        autosync,
        ocr_queue,
        knowledge_engine,
        search_cache,
    ):
        self.catalog = catalog
        self.vector_store = vector_store
        self.autosync = autosync
        self.ocr_queue = ocr_queue
        self.knowledge_engine = knowledge_engine
        self.search_cache = search_cache
        self._lock = threading.RLock()
        self._running = False
        self._state_path = self._resolved(SETTINGS.runtime_path) / "secure_delete_state.json"
        self._state = self._load_state()
        if self._state.get("status") in {"queued", "running"}:
            self._state.update(
                status="interrupted",
                stage="Interrumpida al cerrar LexIA",
                error="La eliminacion fue interrumpida; verifica el documento antes de reintentar.",
            )
            self._save_state()

    def _load_state(self) -> dict:
        try:
            return json.loads(self._state_path.read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError):
            return {"status": "idle", "stage": "", "path": "", "error": ""}

    def _save_state(self) -> None:
        self._state_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self._state_path.with_suffix(".tmp")
        temporary.write_text(json.dumps(self._state, ensure_ascii=False), encoding="utf-8")
        temporary.replace(self._state_path)

    def state(self) -> dict:
        with self._lock:
            return dict(self._state)

    def _set_stage(self, stage: str) -> None:
        with self._lock:
            self._state["stage"] = stage
            self._state["updated_at"] = time.time()
            self._save_state()

    def start_delete(self, path_value) -> bool:
        return self.start_delete_batch([path_value])

    def start_delete_batch(self, path_values) -> bool:
        if not isinstance(path_values, list) or not 1 <= len(path_values) <= 100:
            raise ValueError('Seleccioná entre 1 y 100 archivos para eliminar.')
        paths = list(dict.fromkeys(str(self._validate_path(path)) for path in path_values))
        with self._lock:
            if self._running:
                return False
            ticket = WORK_PRIORITY.reserve()
            self._running = True
            self._state = {
                'status': 'queued', 'stage': 'Eliminación en cola prioritaria',
                'operation_id': ticket, 'path': paths[0], 'name': Path(paths[0]).name,
                'paths': paths, 'total': len(paths), 'completed': 0, 'deleted_paths': [],
                'error': '', 'started_at': time.time(),
            }
            try:
                self._save_state()
                threading.Thread(target=self._delete_batch_worker, args=(paths, ticket),
                                 name='LexIA-Priority-Delete', daemon=True).start()
            except BaseException:
                self._running = False
                WORK_PRIORITY.cancel(ticket)
                raise
        return True

    def _delete_batch_worker(self, paths, ticket):
        try:
            blocker = WORK_PRIORITY.blocker()
            if blocker:
                self._set_stage('Eliminación en cola prioritaria: esperando un punto seguro de ' + blocker)
            with WORK_PRIORITY.deletion(ticket):
                for path in paths:
                    with self._lock:
                        self._state.update(status='running', path=path, name=Path(path).name,
                                           stage='Eliminando archivo')
                        self._save_state()
                    result = self.delete(path)
                    with self._lock:
                        self._state['deleted_paths'].append(path)
                        self._state['completed'] += 1
                        self._state['result'] = result
                        self._save_state()
                with self._lock:
                    self._state.update(status='completed', stage='Eliminación completada',
                                       error='', finished_at=time.time())
                    self._save_state()
        except Exception as error:
            with self._lock:
                self._state.update(status='error', stage='Eliminación detenida',
                                   error=str(error), finished_at=time.time())
                self._save_state()
        finally:
            WORK_PRIORITY.cancel(ticket)
            with self._lock:
                self._running = False

    @staticmethod
    def _resolved(value) -> Path:
        path = Path(value)
        if not path.is_absolute():
            path = Path(__file__).resolve().parents[1] / path
        return path.resolve()

    def _validate_path(self, path_value) -> Path:
        path = self._resolved(path_value)
        library = self._resolved(SETTINGS.library_path)
        try:
            relative = path.relative_to(library)
        except ValueError as error:
            raise PermissionError(
                "Solo se pueden eliminar documentos dentro de la biblioteca LexIA."
            ) from error
        if not relative.parts:
            raise PermissionError("No se puede eliminar la carpeta de la biblioteca.")
        return path

    def _move_to_staging(self, path: Path, staged: Path) -> None:
        try:
            os.replace(path, staged)
            return
        except OSError as original_error:
            if original_error.errno not in {
                errno.EPERM,
                errno.EACCES,
                errno.EXDEV,
            }:
                raise

        if sys.platform == "darwin" and hasattr(os, "chflags"):
            try:
                os.chflags(path, 0)
                os.replace(path, staged)
                return
            except OSError:
                pass

        temporary = staged.with_name(
            f".{staged.name}.{uuid.uuid4().hex}.copying"
        )
        try:
            shutil.copy2(path, temporary)
            if temporary.stat().st_size != path.stat().st_size:
                raise OSError("La copia temporal no coincide con el archivo original.")
            os.replace(temporary, staged)
            path.unlink()
        except Exception:
            temporary.unlink(missing_ok=True)
            if path.exists():
                staged.unlink(missing_ok=True)
            raise

    def _restore_from_staging(self, staged: Path, path: Path) -> None:
        try:
            os.replace(staged, path)
            return
        except OSError:
            pass

        temporary = path.with_name(
            f".{path.name}.{uuid.uuid4().hex}.restoring"
        )
        try:
            shutil.copy2(staged, temporary)
            os.replace(temporary, path)
            staged.unlink(missing_ok=True)
        finally:
            temporary.unlink(missing_ok=True)

    def _vector_count(self, path: Path) -> int:
        result = self.vector_store.client.count(
            collection_name=self.vector_store.collection_name,
            count_filter=models.Filter(
                must=[
                    models.FieldCondition(
                        key="document_path",
                        match=models.MatchValue(value=str(path)),
                    )
                ]
            ),
            exact=True,
        )
        return int(getattr(result, "count", 0) or 0)

    @staticmethod
    def _quote_identifier(value: str) -> str:
        return '"' + value.replace('"', '""') + '"'

    def _delete_ocr_rows(self, path: Path) -> int:
        database = self._resolved(SETTINGS.ocr_queue_path)
        if not database.exists():
            return 0
        removed = 0
        with sqlite3.connect(database) as connection:
            tables = [
                row[0]
                for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                )
                if not str(row[0]).startswith("sqlite_")
            ]
            for table in tables:
                quoted = self._quote_identifier(str(table))
                columns = {
                    row[1]
                    for row in connection.execute(
                        f"PRAGMA table_info({quoted})"
                    )
                }
                if "document_path" in columns:
                    removed += connection.execute(
                        f"DELETE FROM {quoted} WHERE document_path = ?",
                        (str(path),),
                    ).rowcount
        return int(removed)

    def _ocr_count(self, path: Path) -> int:
        database = self._resolved(SETTINGS.ocr_queue_path)
        if not database.exists():
            return 0
        total = 0
        with sqlite3.connect(database) as connection:
            tables = [
                row[0]
                for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                )
                if not str(row[0]).startswith("sqlite_")
            ]
            for table in tables:
                quoted = self._quote_identifier(str(table))
                columns = {
                    row[1]
                    for row in connection.execute(
                        f"PRAGMA table_info({quoted})"
                    )
                }
                if "document_path" in columns:
                    total += int(
                        connection.execute(
                            f"SELECT COUNT(*) FROM {quoted} WHERE document_path = ?",
                            (str(path),),
                        ).fetchone()[0]
                    )
        return total

    def _knowledge_count(self, path: Path) -> int:
        database = self._resolved(SETTINGS.knowledge_path)
        if not database.exists():
            return 0
        total = 0
        with sqlite3.connect(database) as connection:
            tables = [
                row[0]
                for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                )
                if not str(row[0]).startswith("sqlite_")
            ]
            for table in tables:
                quoted = self._quote_identifier(str(table))
                columns = {
                    row[1]
                    for row in connection.execute(
                        f"PRAGMA table_info({quoted})"
                    )
                }
                if "document_path" in columns:
                    total += int(
                        connection.execute(
                            f"SELECT COUNT(*) FROM {quoted} WHERE document_path = ?",
                            (str(path),),
                        ).fetchone()[0]
                    )
        return total

    def _delete_knowledge_rows(self, path: Path) -> int:
        repository = getattr(self.knowledge_engine, "repository", None)
        if repository is None:
            return 0
        return int(repository.remove_path(str(path)) or 0)

    def delete(self, path_value, *, require_duplicate: bool = False) -> dict:
        # Direct navigator/duplicate deletions share the same exclusive gate.
        with WORK_PRIORITY.deletion():
            return self._delete_locked(path_value, require_duplicate=require_duplicate)

    def _delete_locked(self, path_value, *, require_duplicate: bool = False) -> dict:
        path = self._validate_path(path_value)

        staging_root = self._resolved(SETTINGS.runtime_path) / "secure_delete_staging"
        staging_root.mkdir(parents=True, exist_ok=True)
        staged = staging_root / f"{uuid.uuid4().hex}{path.suffix}"
        moved = False

        with self.autosync._sync_lock:
            self._set_stage("Verificando catalogo")
            state = self.catalog.get_file_state(path)
            if state is None:
                raise FileNotFoundError(
                    "El documento ya no existe en el catalogo activo."
                )
            is_duplicate = bool(str(state.get("duplicate_of") or "").strip())
            if require_duplicate and not is_duplicate:
                raise ValueError("El archivo ya no figura como duplicado activo en LexIA.")
            if require_duplicate:
                original = self._validate_path(state['duplicate_of'])
                original_state = self.catalog.get_file_state(original)
                if not original_state or original_state.get('is_deleted') or original_state.get('duplicate_of'):
                    raise ValueError('El original no es un documento principal activo. No se eliminó el archivo.')
                require_identical_files(path, original)

            try:
                if path.exists():
                    if not path.is_file():
                        raise IsADirectoryError(str(path))
                    self._move_to_staging(path, staged)
                    moved = True
                    if require_duplicate:
                        require_identical_files(staged, original)

                self._set_stage("Retirando vectores")
                vectors_before = self._vector_count(path)
                self.vector_store.delete_document(path, wait=True)

                if is_duplicate:
                    # Los duplicados nunca ingresan al Knowledge Engine. No se
                    # consulta ni se modifica esa base: esto evita depender de
                    # esquemas históricos y elimina el error "no such column: path".
                    self._set_stage("Knowledge Engine no aplica a duplicados")
                    knowledge_removed = 0
                else:
                    self._set_stage("Actualizando Knowledge Engine")
                    knowledge_removed = self._delete_knowledge_rows(path)

                self._set_stage("Limpiando OCR, catalogo y fragmentos")
                ocr_removed = self._delete_ocr_rows(path)
                catalog_result = self.catalog.purge_document(path)
                if not catalog_result.get("deleted"):
                    raise RuntimeError("El catalogo no elimino el documento.")

                try:
                    self.search_cache.clear()
                except Exception:
                    pass

                try:
                    self.autosync.library_snapshot.apply_changes(
                        changed_paths=set(),
                        deleted_paths={str(path)},
                    )
                except Exception:
                    snapshot = self._resolved(SETTINGS.runtime_path) / "library_snapshot.json"
                    snapshot.unlink(missing_ok=True)

                if self.catalog.get_file_state(path) is not None:
                    raise RuntimeError("El documento aun figura en el catalogo.")
                if self._ocr_count(path) != 0:
                    raise RuntimeError("El documento aun figura en OCR.")
                if not is_duplicate and self._knowledge_count(path) != 0:
                    raise RuntimeError("El documento aun figura en Knowledge Engine.")
                if staged.exists():
                    if require_duplicate:
                        require_identical_files(staged, original)
                    staged.unlink()

                return {
                    "path": str(path),
                    "name": path.name,
                    "vectors_deleted": vectors_before,
                    "fragments_deleted": int(
                        catalog_result.get("fragments_deleted", 0)
                    ),
                    "ocr_rows_deleted": ocr_removed,
                    "knowledge_rows_deleted": knowledge_removed,
                    "duplicates_released": int(
                        catalog_result.get("duplicates_released", 0)
                    ),
                }
            except Exception:
                if moved and staged.exists() and not path.exists():
                    path.parent.mkdir(parents=True, exist_ok=True)
                    self._restore_from_staging(staged, path)
                raise
