from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_secure_delete_skips_knowledge_entirely_for_duplicates():
    source = (ROOT / "services" / "secure_document_deletion.py").read_text(encoding="utf-8")
    compile(source, str(ROOT / "services" / "secure_document_deletion.py"), "exec")

    assert "is_duplicate = bool" in source
    assert "Knowledge Engine no aplica a duplicados" in source
    assert "knowledge_removed = 0" in source
    assert "if not is_duplicate and self._knowledge_count(path) != 0" in source
    assert "knowledge_engine.sync_paths(" not in source
    assert "knowledge_rows_deleted\": knowledge_removed" in source
