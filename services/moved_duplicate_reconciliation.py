"""Repair a stale original->duplicate relation without moving/deleting files."""
from datetime import datetime
from pathlib import Path
import sqlite3

from config.settings import SETTINGS
from core.file_hasher import FileHasher
from models.document import Document


def reconcile_moved_duplicate(application, path_value):
    root = Path(SETTINGS.library_path).expanduser().resolve()
    path = Path(path_value).expanduser().resolve()
    path.relative_to(root)
    lock = application.autosync._sync_lock
    if not lock.acquire(blocking=False):
        raise RuntimeError('AutoSync está trabajando. Esperá a que termine para corregir la ubicación.')
    try:
        if application.ocr_queue.state().get('running'):
            raise RuntimeError('Esperá a que termine OCR para corregir la ubicación.')
        catalog = application.catalog
        current = catalog.get_file_state(path)
        if not current or current.get('is_deleted') or not current.get('duplicate_of'):
            raise ValueError('El archivo ya no está marcado como duplicado. Actualizá la lista.')
        original = Path(current['duplicate_of']).expanduser().resolve()
        original.relative_to(root)
        if original == path:
            raise ValueError('La referencia apunta al mismo archivo; requiere revisión del catálogo.')
        try:
            original.stat()
        except FileNotFoundError:
            pass
        else:
            raise ValueError('El original todavía existe. No corresponde tratarlo como un traslado.')
        old = catalog.get_file_state(original)
        if old and (old.get('duplicate_of') or not old.get('content_hash')):
            raise ValueError('El registro anterior no tiene una huella principal comprobable; requiere revisión.')
        if current.get('text_content') or current.get('vector_indexed_hash'):
            raise ValueError('La ubicación nueva tiene indexación propia; se conserva para una revisión específica.')
        before = path.stat()
        digest = FileHasher().calculate(path)
        if digest != current.get('content_hash') or (old and digest != old['content_hash']):
            raise ValueError('La huella del archivo no coincide con el original registrado. No se modificó el catálogo.')
        from services.structural_category_policy import classify_structural_path
        category = classify_structural_path(path, library_root=root).category
        document = Document(name=path.name, path=path, category=category,
                            extension=path.suffix.lower(), size=before.st_size,
                            modified_ns=before.st_mtime_ns, content_hash=digest)

        # Back up every local DB modified below, while AutoSync is locked.
        backup = Path(SETTINGS.runtime_path) / 'backups' / ('moved-duplicate-' + datetime.now().strftime('%Y%m%d-%H%M%S-%f'))
        backup.mkdir(parents=True)
        for label, database in [('catalog', catalog.database_path),
                                ('knowledge', getattr(SETTINGS, 'knowledge_path', None)),
                                ('ocr', getattr(SETTINGS, 'ocr_queue_path', None))]:
            if database is None or not Path(database).is_file():
                continue
            source = sqlite3.connect(Path(database).resolve().as_uri() + '?mode=ro', uri=True)
            destination = sqlite3.connect(backup / (label + '.sqlite3'))
            try:
                source.backup(destination, pages=1024)
            finally:
                destination.close()
                source.close()
        after = path.stat()
        if (before.st_ino, before.st_size, before.st_mtime_ns, before.st_ctime_ns) != (after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns) or original.exists():
            raise ValueError('Las ubicaciones cambiaron durante la comprobación. No se modificó el catálogo.')
        if old is None:
            catalog.release_orphan_duplicate(path, original, digest)
            warnings = ['La entrada antigua ya no existe. Se quitó la marca de duplicado; la extracción local del texto queda pendiente de AutoSync.']
            try:
                application.autosync.notify_change('modified', str(path), False)
            except Exception:
                warnings.append('Ejecutá una sincronización para procesar este archivo.')
            return {'reconciled': str(path), 'old_path': str(original), 'backup': str(backup), 'warnings': warnings}
        result = catalog.relocate_documents_batch([(str(original), document)], recover_deleted=True)
        if result.get('relocated') != 1 or result.get('failed'):
            raise RuntimeError('No se pudo reconciliar la ubicación. Se conserva el respaldo: ' + str(backup))
        warnings = []
        ocr_path = getattr(SETTINGS, 'ocr_queue_path', None)
        if ocr_path and Path(ocr_path).is_file():
            try:
                with sqlite3.connect(str(ocr_path), timeout=10) as connection:
                    connection.execute('UPDATE ocr_queue SET document_path=?, document_name=? WHERE document_path=? AND NOT EXISTS(SELECT 1 FROM ocr_queue WHERE document_path=?)', (str(path), path.name, str(original), str(path)))
            except Exception as error:
                warnings.append('Cola OCR pendiente: ' + str(error))
        try:
            application.knowledge_engine.move_documents([(str(original), str(path))])
        except Exception as error:
            warnings.append('Knowledge pendiente: ' + str(error))
        try:
            application.indexer.run(target_paths=[str(path)])
        except Exception as error:
            warnings.append('Vínculos vectoriales pendientes: ' + str(error))
        try:
            application.autosync.library_snapshot.apply_changes(changed_paths={str(path)}, deleted_paths={str(original)})
        except Exception as error:
            warnings.append('Registro de carpetas pendiente: ' + str(error))
        if warnings:
            try:
                application.autosync.request_full_scan('moved_duplicate_repair')
            except Exception:
                warnings.append('Ejecutá una sincronización para completar los vínculos pendientes.')
        cache = getattr(application, 'search_cache', None)
        if cache is not None:
            try:
                cache.clear()
            except Exception:
                warnings.append('Caché de búsqueda pendiente de renovar.')
        return {'reconciled': str(path), 'old_path': str(original), 'backup': str(backup), 'warnings': warnings}
    finally:
        lock.release()
