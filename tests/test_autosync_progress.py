"""Fixture-only progress tests; never start services or open the real catalog."""
import importlib.util
import sys
import threading
from pathlib import Path
from types import SimpleNamespace

import pytest

from core.document_detector import DocumentDetector
from services.library_snapshot_service import LibrarySnapshotService


@pytest.fixture
def sync_module(monkeypatch):
    # Progress/event tests don't extract documents. Isolate the heavyweight OCR
    # pipeline import, while exercising the real AutoSync and Watchdog handlers.
    with monkeypatch.context() as patch:
        patch.setitem(sys.modules, 'core.pipeline', SimpleNamespace(DocumentPipeline=object))
        spec = importlib.util.spec_from_file_location('autosync_progress_fixture', 'services/autosync_service.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    return module


@pytest.fixture
def service(sync_module, tmp_path):
    service = sync_module.AutoSyncService.__new__(sync_module.AutoSyncService)
    service._state_lock = threading.RLock()
    service._event_lock = threading.RLock()
    service._changed = threading.Event()
    service._changed_files = set()
    service._deleted_files = set()
    service._moved_files = []
    service._state = {'phase': 'idle', 'recent_files': []}
    service._full_scan_requested = False
    service.state_path = tmp_path / 'state.json'
    service.logger = SimpleNamespace(exception=lambda *args: None)
    return service


def test_snapshot_progress_counts_real_documents_and_excludes_auxiliary_files(tmp_path):
    library = tmp_path / 'library'
    library.mkdir()
    for name in ['one.pdf', 'two.txt', '._one.pdf', '~$draft.docx', '.DS_Store', '_DS_Store']:
        (library / name).write_text('fixture')
    service = LibrarySnapshotService(library, tmp_path / 'snapshot.json', DocumentDetector.SUPPORTED_EXTENSIONS)
    reports = []
    changed, deleted, snapshot = service.scan(lambda *args: reports.append(args))
    assert {Path(path).name for path in changed} == {'one.pdf', 'two.txt'}
    assert deleted == set()
    assert reports[0] == (0, 0, '')
    assert any(done > 0 and total == 0 for done, total, _ in reports[:-1])
    assert reports[-1][:2] == (2, 2)
    assert len(snapshot) == 2
    detected = DocumentDetector(library).scan()
    assert {doc.name for doc in detected} == {'one.pdf', 'two.txt'}


def test_folder_move_schedules_reconciliation(sync_module, service):
    handler = sync_module._LibraryEventHandler(service.notify_change, service.notify_move)
    handler.on_moved(SimpleNamespace(is_directory=True, src_path='/library/old', dest_path='/library/new'))
    assert service._full_scan_requested
    assert service._changed.is_set()
    assert service.state()['scan_mode'] == 'folder_reorganized'


@pytest.mark.parametrize('name', ['.DS_Store', '_DS_Store', '._document.pdf', '~$document.docx', 'desktop.ini'])
def test_auxiliary_events_never_change_visible_progress(service, tmp_path, name):
    service.notify_change('modified', str(tmp_path / name), False)
    assert not service._changed.is_set()
    assert service.state()['phase'] == 'idle'


def test_new_changes_do_not_replace_an_active_progress_counter(service):
    service._publish_progress('relocate', 'Moviendo referencias', 12, 40, '/library/one.pdf')
    service.request_full_scan('folder_reorganized')
    state = service.state()
    assert state['phase'] == 'scanning'
    assert (state['processed'], state['total']) == (12, 40)
    assert state['progress_label'] == 'Moviendo referencias'
    assert state['pending_changes'] is True


def test_progress_is_stage_specific_bounded_and_not_externally_mutable(service):
    for n in range(65):
        service._publish_progress('relocate', 'Ruta actualizada', n + 1, 65,
                                  f'/new/{n}.pdf', source=f'/old/{n}.pdf', finished=True)
    state = service.state()
    assert len(state['recent_files']) == 50
    assert state['percentage'] == 100
    assert state['recent_files'][-1]['source'] == '/old/64.pdf'
    state['recent_files'][-1]['path'] = 'wrong'
    assert service.state()['recent_files'][-1]['path'] == '/new/64.pdf'
    service._publish_progress('snapshot', 'Explorando', 350, 0, total_known=False)
    assert service.state()['processed'] == 350
    assert service.state()['progress_total_known'] is False
    assert service.state()['percentage'] == 0


def test_tracked_paths_report_before_and_after_each_document(service):
    files = ['/library/one.pdf', '/library/two.pdf']
    during = []
    for path in service._tracked_paths(files, 'Comparando', 'compare'):
        during.append((path, service.state()['processed']))
    assert during == [(files[0], 0), (files[1], 1)]
    assert service.state()['processed'] == 2
    assert all(item['status'] == 'Revisado' for item in service.state()['recent_files'])
