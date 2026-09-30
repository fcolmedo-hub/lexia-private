from pathlib import Path
import hashlib
import os
import sqlite3
import tempfile
import threading
from types import SimpleNamespace
import unittest
import importlib
import ast
import sys
from unittest.mock import Mock, patch

from models.document import Document
from models.fragment import Fragment
from storage.catalog import DocumentCatalog
from services.duplicate_file_safety import duplicate_problem, require_identical_files, identical_duplicates
from services import moved_duplicate_reconciliation as repair


class MovedDuplicateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.library = self.root / 'library'
        self.old = self.library / 'Escritos/Administrativos/original.doc'
        self.new = self.library / 'Escritos/Tributario/original.doc'
        self.old.parent.mkdir(parents=True)
        self.new.parent.mkdir(parents=True)
        self.old.write_bytes(b'legal document contents')
        self.digest = hashlib.sha256(self.old.read_bytes()).hexdigest()
        self.catalog = DocumentCatalog(self.root / 'catalog.sqlite3')
        doc = Document(name=self.old.name, path=self.old, category='Escritos',
                       size=self.old.stat().st_size, modified_ns=self.old.stat().st_mtime_ns,
                       content_hash=self.digest, text='Texto original ya extraído',
                       fragments=[Fragment(self.old.name,self.old,'Escritos',0,'Texto original ya extraído',0,25)])
        self.catalog.save(doc)
        with self.catalog._connect() as db:
            db.execute('UPDATE documents SET vector_indexed_hash=? WHERE path=?', (self.digest,str(self.old)))
        self.old.rename(self.new)
        duplicate = Document(name=self.new.name,path=self.new,category='Escritos',
                             size=self.new.stat().st_size,modified_ns=self.new.stat().st_mtime_ns,
                             content_hash=self.digest,duplicate_of=str(self.old),extraction_method='duplicate')
        self.catalog.save(duplicate)
        self.settings = SimpleNamespace(library_path=self.library,runtime_path=self.root/'runtime',knowledge_path=self.root/'knowledge.sqlite3')
        self.app = SimpleNamespace(catalog=self.catalog,
            ocr_queue=SimpleNamespace(state=lambda:{'running':False}),
            autosync=SimpleNamespace(_sync_lock=threading.Lock(),library_snapshot=Mock(),request_full_scan=Mock(),notify_change=Mock()),
            knowledge_engine=Mock(),indexer=Mock(),search_cache=Mock())
        p=patch.object(repair,'SETTINGS',self.settings);p.start();self.addCleanup(p.stop)

    def test_missing_original_is_not_a_duplicate_candidate(self):
        self.assertIsNone(self.catalog.find_path_by_hash(self.digest, str(self.new)))
        self.assertTrue(duplicate_problem(self.new,self.old))
        with self.assertRaises(ValueError):require_identical_files(self.new,self.old)
        self.assertTrue(self.new.is_file())

    def test_real_identical_copies_pass_different_or_same_file_fail(self):
        self.old.write_bytes(self.new.read_bytes())
        require_identical_files(self.new,self.old)
        self.old.write_bytes(b'completely different')
        with self.assertRaises(ValueError):require_identical_files(self.new,self.old)
        with self.assertRaises(ValueError):require_identical_files(self.new,self.new)
        self.old.unlink();os.link(self.new,self.old)
        with self.assertRaises(ValueError):require_identical_files(self.new,self.old)

    def test_repair_preserves_file_text_fragments_and_vector_relocation(self):
        content=self.new.read_bytes()
        result=repair.reconcile_moved_duplicate(self.app,str(self.new))
        state=self.catalog.get_file_state(self.new)
        self.assertIsNone(state['duplicate_of'])
        self.assertEqual(state['text_content'],'Texto original ya extraído')
        self.assertIsNone(self.catalog.get_file_state(self.old))
        self.assertEqual(self.new.read_bytes(),content)
        self.assertFalse(self.old.exists())
        with self.catalog._connect() as db:
            self.assertEqual(db.execute('SELECT count(*) FROM fragments WHERE document_path=?',(str(self.new),)).fetchone()[0],1)
            self.assertEqual(db.execute('SELECT count(*) FROM fragments_fts WHERE document_path=?',(str(self.new),)).fetchone()[0],1)
        self.assertEqual(self.catalog.pending_vector_relocations()[0]['new_path'],str(self.new))
        self.assertTrue((Path(result['backup'])/'catalog.sqlite3').is_file())
        self.app.knowledge_engine.move_documents.assert_called_once_with([(str(self.old),str(self.new))])
        self.app.indexer.run.assert_called_once_with(target_paths=[str(self.new)])
        with self.assertRaises(ValueError):repair.reconcile_moved_duplicate(self.app,str(self.new))

    def test_changed_contents_or_existing_original_never_reconciled(self):
        self.new.write_bytes(b'changed')
        with self.assertRaises(ValueError):repair.reconcile_moved_duplicate(self.app,str(self.new))
        self.assertEqual(self.catalog.get_file_state(self.new)['duplicate_of'],str(self.old))
        self.old.write_bytes(b'another file')
        with self.assertRaises(ValueError):repair.reconcile_moved_duplicate(self.app,str(self.new))
        self.assertTrue(self.old.exists())

    def test_busy_sync_defers_repair(self):
        self.app.autosync._sync_lock.acquire()
        try:
            with self.assertRaises(RuntimeError):repair.reconcile_moved_duplicate(self.app,str(self.new))
        finally:self.app.autosync._sync_lock.release()
        self.assertEqual(self.catalog.get_file_state(self.new)['duplicate_of'],str(self.old))

    def duplicate_snapshot(self):
        # Exercise the real snapshot SQL and eligibility without starting HTTP/Qdrant.
        source = Path(__file__).resolve().parents[1] / 'services/windows_research_manual_sources.py'
        node = next(n for n in ast.parse(source.read_text()).body if isinstance(n, ast.FunctionDef) and n.name == '_duplicates_snapshot')
        namespace = {'Path': Path, 'sqlite3': sqlite3, 'SETTINGS': SimpleNamespace(catalog_path=self.catalog.database_path), 'duplicate_problem': duplicate_problem, 'identical_duplicates': identical_duplicates}
        exec(compile(ast.Module(body=[node], type_ignores=[]), str(source), 'exec'), namespace)
        return namespace['_duplicates_snapshot']()

    def test_deleted_original_shows_repair_and_restores_text_and_search(self):
        self.catalog.mark_paths_deleted({str(self.old)})
        self.assertEqual(self.duplicate_snapshot(), [])
        before = self.new.read_bytes()
        result = repair.reconcile_moved_duplicate(self.app, str(self.new))
        current = self.catalog.get_file_state(self.new)
        self.assertFalse(current['is_deleted'])
        self.assertIsNone(current['duplicate_of'])
        self.assertIsNone(current['vector_indexed_hash'])
        self.assertEqual(current['text_content'], 'Texto original ya extraído')
        with self.catalog._connect() as db:
            self.assertEqual(db.execute('SELECT count(*) FROM fragments_fts WHERE document_path=?', (str(self.new),)).fetchone()[0], 1)
        self.assertEqual(self.new.read_bytes(), before)
        self.assertFalse(self.old.exists())
        self.assertFalse(self.duplicate_snapshot())
        self.assertEqual(self.catalog.pending_vector_relocation_count(), 0)
        self.app.indexer.run.assert_called_once_with(target_paths=[str(self.new)])
        with sqlite3.connect(Path(result['backup'])/'catalog.sqlite3') as db:
            self.assertEqual(db.execute('SELECT is_deleted FROM documents WHERE path=?', (str(self.old),)).fetchone()[0], 1)

    def test_missing_original_row_releases_only_flag_and_queues_local_extraction(self):
        with self.catalog._connect() as db:
            db.execute('DELETE FROM documents WHERE path=?', (str(self.old),))
        self.assertEqual(self.duplicate_snapshot(), [])
        before = self.new.read_bytes()
        result = repair.reconcile_moved_duplicate(self.app, str(self.new))
        current = self.catalog.get_file_state(self.new)
        self.assertIsNone(current['duplicate_of'])
        self.assertEqual(current['extraction_method'], '')
        self.assertEqual(self.new.read_bytes(), before)
        self.assertTrue(result['warnings'])
        self.app.autosync.notify_change.assert_called_once_with('modified', str(self.new), False)
        self.app.indexer.run.assert_not_called()

    def test_inactive_original_hash_mismatch_keeps_both_records(self):
        self.catalog.mark_paths_deleted({str(self.old)})
        with self.catalog._connect() as db:
            db.execute('UPDATE documents SET content_hash=? WHERE path=?', ('wrong', str(self.old)))
        with self.assertRaises(ValueError): repair.reconcile_moved_duplicate(self.app, str(self.new))
        self.assertTrue(self.catalog.get_file_state(self.old)['is_deleted'])
        self.assertEqual(self.catalog.get_file_state(self.new)['duplicate_of'], str(self.old))

    def test_missing_original_and_changed_file_is_not_released(self):
        with self.catalog._connect() as db:
            db.execute('DELETE FROM documents WHERE path=?', (str(self.old),))
        self.new.write_bytes(b'changed after indexing')
        with self.assertRaises(ValueError): repair.reconcile_moved_duplicate(self.app, str(self.new))
        self.assertEqual(self.catalog.get_file_state(self.new)['duplicate_of'], str(self.old))

    def test_recovery_does_not_replace_independently_indexed_new_path(self):
        self.catalog.mark_paths_deleted({str(self.old)})
        with self.catalog._connect() as db:
            db.execute('UPDATE documents SET text_content=? WHERE path=?', ('Independent text', str(self.new)))
        with self.assertRaises(ValueError): repair.reconcile_moved_duplicate(self.app, str(self.new))
        self.assertEqual(self.catalog.get_file_state(self.new)['text_content'], 'Independent text')

    def test_list_requires_identical_existing_files_in_distinct_folders(self):
        self.assertEqual(self.duplicate_snapshot(), [])
        self.old.write_bytes(self.new.read_bytes())
        self.assertTrue(self.duplicate_snapshot()[0]['verified_identical'])
        self.old.write_bytes(b'X' * self.new.stat().st_size)
        self.assertEqual(self.duplicate_snapshot(), [])
        sibling = self.new.with_name('same-folder-copy.doc')
        sibling.write_bytes(self.new.read_bytes())
        self.assertFalse(identical_duplicates(self.new, sibling))
        self.assertIsNone(self.catalog.find_path_by_hash(self.digest, str(self.new)))

    def test_byte_verification_cache_invalidates_after_same_size_edit(self):
        from services import duplicate_file_safety as safety
        self.old.write_bytes(self.new.read_bytes())
        with patch.object(safety, 'require_identical_files', wraps=safety.require_identical_files) as check:
            self.assertTrue(identical_duplicates(self.new, self.old))
            self.assertTrue(identical_duplicates(self.new, self.old))
            self.assertEqual(check.call_count, 1)
            self.old.write_bytes(b'X' * self.new.stat().st_size)
            self.assertFalse(identical_duplicates(self.new, self.old))
            self.assertEqual(check.call_count, 2)

    def test_automatic_batch_repairs_two_tombstones_with_one_backup_and_index_pass(self):
        from services.automatic_duplicate_reconciliation import reconcile_pass
        second_old = self.old.with_name('second.doc')
        second_new = self.new.with_name('second.doc')
        second_new.write_bytes(b'second contents')
        digest = hashlib.sha256(second_new.read_bytes()).hexdigest()
        self.catalog.save(Document(name=second_old.name, path=second_old, category='Escritos', content_hash=digest, text='Second text'))
        self.catalog.save(Document(name=second_new.name, path=second_new, category='Escritos', content_hash=digest, duplicate_of=str(second_old), extraction_method='duplicate'))
        self.catalog.mark_paths_deleted({str(self.old), str(second_old)})
        result = reconcile_pass(self.app)
        self.assertEqual(result['repaired'], 2)
        self.assertEqual(result['failed'], 0)
        self.assertEqual(len(list((self.settings.runtime_path/'backups').iterdir())), 1)
        self.app.indexer.run.assert_called_once_with(target_paths=sorted([str(self.new), str(second_new)]))
        self.assertEqual(self.catalog.get_file_state(second_new)['text_content'], 'Second text')
        self.assertIsNone(self.catalog.get_file_state(self.new)['duplicate_of'])
        self.assertTrue(self.new.exists())
        self.assertTrue(second_new.exists())
        self.assertFalse(self.duplicate_snapshot())

    def test_automatic_pass_waits_for_sync_or_ocr(self):
        from services.automatic_duplicate_reconciliation import reconcile_pass
        self.app.autosync._sync_lock.acquire()
        try: self.assertTrue(reconcile_pass(self.app)['deferred'])
        finally: self.app.autosync._sync_lock.release()
        self.app.ocr_queue.state=lambda: {'running': True}
        self.assertTrue(reconcile_pass(self.app)['deferred'])
        self.assertEqual(self.catalog.get_file_state(self.new)['duplicate_of'], str(self.old))

    def test_background_worker_repairs_without_user_action_and_stops(self):
        from services.automatic_duplicate_reconciliation import AutomaticDuplicateReconciler
        self.catalog.mark_paths_deleted({str(self.old)})
        worker = AutomaticDuplicateReconciler(self.app)
        self.addCleanup(worker.stop)
        worker.request()
        worker._thread.join(timeout=5)
        self.assertFalse(worker.snapshot()['running'])
        self.assertEqual(worker.snapshot()['repaired'], 1)
        self.assertIsNone(self.catalog.get_file_state(self.new)['duplicate_of'])
        thread = worker._thread
        worker.request()
        self.assertIs(worker._thread, thread)
        worker.stop()
        self.assertFalse(thread.is_alive())

    def test_automatic_hash_mismatch_keeps_file_and_reports_pending(self):
        from services.automatic_duplicate_reconciliation import reconcile_pass
        self.new.write_bytes(b'Changed content')
        with self.assertLogs('services.automatic_duplicate_reconciliation', level='WARNING'):
            result = reconcile_pass(self.app)
        self.assertEqual(result['failed'], 1)
        self.assertEqual(result['repaired'], 0)
        self.assertEqual(self.new.read_bytes(), b'Changed content')
        self.assertEqual(self.duplicate_snapshot(), [])

    def test_pipeline_automatically_restores_inactive_original(self):
        # Use the production pipeline methods without loading OCR/model dependencies.
        from typing import Callable
        from core.file_hasher import FileHasher
        source = Path(__file__).resolve().parents[1] / 'core/pipeline.py'
        cls = next(n for n in ast.parse(source.read_text()).body if isinstance(n, ast.ClassDef) and n.name=='DocumentPipeline')
        cls.body = [n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name in {'_state_is_complete', '_process_document'}]
        namespace = {'Path': Path, 'Callable': Callable}
        exec(compile(ast.Module(body=[cls],type_ignores=[]),str(source),'exec'), namespace)
        pipeline = namespace['DocumentPipeline']()
        pipeline.catalog = self.catalog
        pipeline.hasher = FileHasher()
        pipeline.extractor = Mock(side_effect=AssertionError('must preserve existing text'))
        self.catalog.mark_paths_deleted({str(self.old)})
        document = Document(name=self.new.name,path=self.new,category='Escritos')
        stats = {'relocated': 0}
        pipeline._process_document(document, stats, {str(self.new)})
        self.assertEqual(stats['relocated'], 1)
        self.assertEqual(self.catalog.get_file_state(self.new)['text_content'], 'Texto original ya extraído')
        self.assertFalse(self.duplicate_snapshot())

    def test_vector_failure_keeps_file_and_catalog_with_pending_relocation(self):
        self.app.indexer.run.side_effect=RuntimeError('Qdrant offline')
        result=repair.reconcile_moved_duplicate(self.app,str(self.new))
        self.assertTrue(result['warnings'])
        self.assertIsNone(self.catalog.get_file_state(self.new)['duplicate_of'])
        self.assertTrue(self.new.exists())
        self.assertEqual(self.catalog.pending_vector_relocation_count(),1)
        self.app.autosync.request_full_scan.assert_called_once()

    def test_delete_service_blocks_missing_or_different_original_before_any_removal(self):
        # Qdrant is not exercised: the guard must reject before any index access.
        try:
            deletion = importlib.import_module('services.secure_document_deletion')
        except ModuleNotFoundError as error:
            if error.name != 'qdrant_client':raise
            with patch.dict(sys.modules, {'qdrant_client': SimpleNamespace(models=SimpleNamespace())}):
                deletion = importlib.import_module('services.secure_document_deletion')
        service = deletion.SecureDocumentDeletionService.__new__(deletion.SecureDocumentDeletionService)
        service.catalog=self.catalog
        service.ocr_queue=self.app.ocr_queue
        service.autosync=self.app.autosync
        service._set_stage=Mock()
        service._move_to_staging=Mock(side_effect=AssertionError('must not move file'))
        with patch.object(deletion,'SETTINGS',self.settings):
            with self.assertRaises(ValueError):service.delete(self.new,require_duplicate=True)
            self.old.write_bytes(b'different contents')
            with self.assertRaises(ValueError):service.delete(self.new,require_duplicate=True)
        service._move_to_staging.assert_not_called()
        self.assertTrue(self.new.is_file())
        self.assertEqual(self.catalog.get_file_state(self.new)['duplicate_of'],str(self.old))


if __name__=='__main__':unittest.main()
