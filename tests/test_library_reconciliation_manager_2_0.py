from pathlib import Path


def test_library_reconciliation_manager_2_0():
    root = Path(__file__).parents[1]
    settings = (root / "config/settings.py").read_text(encoding="utf-8")
    autosync = (root / "services/autosync_service.py").read_text(encoding="utf-8")
    vector = (root / "search/vector_store.py").read_text(encoding="utf-8")
    indexer = (root / "search/indexer.py").read_text(encoding="utf-8")
    ocr = (root / "services/ocr_queue_service.py").read_text(encoding="utf-8")
    pipeline = (root / "core/pipeline.py").read_text(encoding="utf-8")
    ui = (root / "app/ui.py").read_text(encoding="utf-8")
    assert "qdrant_timeout_seconds: int = 120" in settings
    assert "qdrant_upsert_batch_size: int = 256" in settings
    assert "def _upsert_points_in_batches(" in vector
    assert "qdrant_upsert_retries" in vector
    assert "def request_stop(" in ocr
    assert "cancel_callback=self._cancel_requested.is_set" in ocr
    assert "cancel_callback: Callable[[], bool]" in pipeline
    assert "def request_stop(self)" in indexer
    assert "def preview_reconciliation(" in autosync
    assert "def set_configuration(" in autosync
    assert "def _scheduled_due(" in autosync
    assert "def reconcile_paths(" in autosync
    assert 'st.code(item["document_path"]' in ui
    assert '"Confirmar eliminacion"' in ui
    assert "Escribi ELIMINAR" not in ui
    assert all(label in ui for label in ("Manual", "Automático", "Programado"))
