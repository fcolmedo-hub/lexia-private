from pathlib import Path


def test_performance_recovery_2_3():
    root = Path(__file__).parents[1]
    embedding = (root / "search/embedding_service.py").read_text(encoding="utf-8")
    vector = (root / "search/vector_store.py").read_text(encoding="utf-8")
    indexer = (root / "search/indexer.py").read_text(encoding="utf-8")
    catalog = (root / "storage/catalog.py").read_text(encoding="utf-8")
    ocr = (root / "services/ocr_queue_service.py").read_text(encoding="utf-8")
    deletion = (root / "services/secure_document_deletion.py").read_text(encoding="utf-8")
    ui = (root / "app/ui.py").read_text(encoding="utf-8")
    assert "self._model = None" in embedding
    assert vector.index("collection_exists") < vector.index("dimension =")
    assert "pending_vector_documents(" in indexer
    assert "paths=target_paths" in indexer
    assert "paths: list[str | Path] | None = None" in catalog
    assert (root / "core/ocr_worker.py").exists()
    assert "target_paths=[path]" in ocr
    assert "recover_interrupted" in ocr
    assert "def start_delete(" in deletion
    assert deletion.count("_vector_count(path)") == 1
    assert "inspector_folder_multiselect" in ui

