from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_secure_delete_handles_duplicate_knowledge_without_sync_paths():
    source = (ROOT / "services" / "secure_document_deletion.py").read_text(encoding="utf-8")
    compile(source, str(ROOT / "services" / "secure_document_deletion.py"), "exec")

    assert "is_duplicate = bool" in source
    assert "Omitiendo Knowledge Engine para duplicado" in source
    assert "repository.remove_path(str(path))" in source
    assert "knowledge_rows_deleted\": knowledge_removed" in source
    assert "knowledge_engine.sync_paths(" not in source
