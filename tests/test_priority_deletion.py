import ast
from pathlib import Path
import logging
import sys
import tempfile
import threading
import time
from time import perf_counter
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

sys.modules.setdefault('qdrant_client', SimpleNamespace(models=SimpleNamespace()))
from services.library_work_priority import WORK_PRIORITY as work, DeletionPriorityYield
from services import secure_document_deletion as deletion


class PriorityDeletionTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.library=self.root/'library';self.library.mkdir()
        self.paths=[]
        for n in range(3):
            p=self.library/f'{n}.txt';p.write_text('file '+str(n));self.paths.append(str(p))
        self.settings=SimpleNamespace(library_path=self.library,runtime_path=self.root/'runtime')
        p=patch.object(deletion,'SETTINGS',self.settings);p.start();self.addCleanup(p.stop)
        self.events=[]
        test=self
        class Service(deletion.SecureDocumentDeletionService):
            def _delete_locked(self,path_value,**kwargs):
                p=self._validate_path(path_value)
                if getattr(self,'fail','')==str(p):raise RuntimeError('locked file')
                test.events.append('delete '+p.name);p.unlink()
                return {'deleted':str(p)}
        self.service=Service(Mock(),Mock(),SimpleNamespace(_sync_lock=threading.RLock()),Mock(),Mock(),Mock())

    def finished(self):
        deadline=time.monotonic()+4
        while time.monotonic()<deadline:
            if not self.service._running:return self.service.state()
            threading.Event().wait(.01)
        self.fail('worker did not finish')

    def test_queued_batch_waits_for_document_then_precedes_background_resume(self):
        entered,release,resumed=threading.Event(),threading.Event(),threading.Event()
        def ocr():
            with work.background('OCR'):
                entered.set();release.wait(3);self.events.append('OCR current done')
            with work.background('OCR'):
                self.events.append('OCR resumed');resumed.set()
        t=threading.Thread(target=ocr);t.start();self.assertTrue(entered.wait(2))
        self.assertTrue(self.service.start_delete_batch(self.paths))
        self.assertEqual(self.service.state()['status'],'queued')
        self.assertTrue(all(Path(p).exists() for p in self.paths))
        self.assertFalse(self.service.start_delete(self.paths[0]))
        release.set();state=self.finished();self.assertTrue(resumed.wait(2));t.join(2)
        self.assertEqual(state['completed'],3)
        self.assertEqual(self.events,['OCR current done','delete 0.txt','delete 1.txt','delete 2.txt','OCR resumed'])
        self.assertFalse(work.pending())

    def test_failure_stops_batch_keeps_unattempted_files_and_releases_priority(self):
        self.service.fail=self.paths[1]
        self.service.start_delete_batch(self.paths);state=self.finished()
        self.assertEqual(state['status'],'error');self.assertEqual(state['completed'],1)
        self.assertEqual(state['deleted_paths'],[self.paths[0]])
        self.assertFalse(Path(self.paths[0]).exists());self.assertTrue(Path(self.paths[1]).exists());self.assertTrue(Path(self.paths[2]).exists())
        with work.background('resume'):pass
        self.assertFalse(work.pending())

    def test_validate_entire_batch_before_reserving_or_deleting(self):
        with self.assertRaises(PermissionError):self.service.start_delete_batch([self.paths[0],str(self.root/'outside.txt')])
        self.assertTrue(Path(self.paths[0]).exists());self.assertFalse(work.pending())

    def test_restart_marks_queued_job_interrupted_without_replaying(self):
        self.service._state.update(status='queued',paths=self.paths)
        self.service._save_state()
        other=deletion.SecureDocumentDeletionService(Mock(),Mock(),Mock(),Mock(),Mock(),Mock())
        self.assertEqual(other.state()['status'],'interrupted')
        self.assertTrue(all(Path(p).exists() for p in self.paths))

    def test_actual_ocr_loop_yields_between_files_and_skips_deleted_path(self):
        from datetime import datetime
        source=Path(__file__).resolve().parents[1]/'services/ocr_queue_service.py'
        cls=next(n for n in ast.parse(source.read_text()).body if isinstance(n,ast.ClassDef) and n.name=='OCRQueueService')
        cls.body=[n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name=='_process']
        entered,release=threading.Event(),threading.Event()
        seen=[]
        def run(**kwargs):
            path=kwargs['changed_paths'][0];seen.append(path)
            if path==self.paths[0]:entered.set();release.wait(3)
            return SimpleNamespace(detected=0)
        factory=Mock();factory.return_value.run.side_effect=run
        ns={'Path':Path,'WORK_PRIORITY':work,'datetime':datetime,'DocumentPipeline':factory}
        exec(compile(ast.Module(body=[cls],type_ignores=[]),str(source),'exec'),ns)
        ocr=ns['OCRQueueService']();ocr._cancel_requested=threading.Event()
        ocr.repository=Mock();ocr.repository.get.return_value={}
        ocr.indexer=Mock();ocr._publish_page_progress=Mock()
        thread=threading.Thread(target=ocr._process,args=(self.paths,));thread.start()
        try:
            self.assertTrue(entered.wait(2))
            self.assertTrue(self.service.start_delete_batch([self.paths[1]]))
        finally:release.set()
        self.finished();thread.join(3)
        self.assertFalse(thread.is_alive())
        self.assertEqual(seen,[self.paths[0],self.paths[2]])
        self.assertFalse(ocr._running);self.assertEqual(ocr._state['error'],'')

    def test_autosync_yields_and_requeues_fresh_scan_without_error(self):
        source=Path(__file__).resolve().parents[1]/'services/autosync_service.py'
        tree=ast.parse(source.read_text());cls=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='AutoSyncService')
        method=next(n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name=='_execute')
        cls.body=[method]
        ns={'WORK_PRIORITY':work,'DeletionPriorityYield':DeletionPriorityYield,'perf_counter':perf_counter,'datetime':Mock()}
        exec(compile(ast.Module(body=[cls],type_ignores=[]),str(source),'exec'),ns)
        service=ns['AutoSyncService']();service._sync_lock=threading.RLock();service.logger=Mock();service.request_full_scan=Mock()
        ticket=[];states=[]
        def update(**values):
            states.append(values)
            if not ticket:ticket.append(work.reserve())
        service._update=update
        try:service._execute(False,set(self.paths),set())
        finally:
            for value in ticket:work.cancel(value)
        service.request_full_scan.assert_called_once_with('resume_after_priority_deletion')
        self.assertEqual(states[-1]['phase'],'waiting');self.assertIsNone(states[-1]['last_error'])

    def test_pipeline_pause_does_not_mark_unvisited_paths_deleted(self):
        from typing import Callable,Iterable
        source=Path(__file__).resolve().parents[1]/'core/pipeline.py'
        cls=next(n for n in ast.parse(source.read_text()).body if isinstance(n,ast.ClassDef) and n.name=='DocumentPipeline')
        cls.body=[n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name=='run']
        ns={'Path':Path,'Callable':Callable,'Iterable':Iterable,'PipelineResult':object,'PipelineCancelled':RuntimeError,
            'DeletionPriorityYield':DeletionPriorityYield,'SETTINGS':SimpleNamespace(checkpoint_every_documents=100)}
        exec(compile(ast.Module(body=[cls],type_ignores=[]),str(source),'exec'),ns)
        pipeline=ns['DocumentPipeline']();pipeline.detector=Mock();pipeline.jobs=Mock();pipeline.catalog=Mock()
        pipeline.detector.scan.return_value=[SimpleNamespace(path=Path(p)) for p in self.paths]
        tickets=[]
        def process(*args,**kwargs):tickets.append(work.reserve())
        pipeline._process_document=Mock(side_effect=process)
        try:
            with work.background('AutoSync'):
                with self.assertRaises(DeletionPriorityYield):pipeline.run(progress_callback=lambda *args:work.checkpoint())
        finally:
            for ticket in tickets:work.cancel(ticket)
        self.assertEqual(pipeline._process_document.call_count,1)
        pipeline.catalog.mark_missing_as_deleted.assert_not_called()
        self.assertEqual(pipeline.jobs.finish.call_args.args[1],'interrupted')

if __name__=='__main__':unittest.main()
