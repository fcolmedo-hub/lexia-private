from pathlib import Path


def test_secure_document_deletion_1_8():
    root = Path(__file__).parents[1]
    ui = (root / "app" / "ui.py").read_text(encoding="utf-8")
    catalog = (root / "storage" / "catalog.py").read_text(encoding="utf-8")
    app = (root / "services" / "application.py").read_text(encoding="utf-8")
    service = (root / "services" / "secure_document_deletion.py").read_text(encoding="utf-8")
    assert "def purge_document(self, path" in catalog
    assert "def secure_document_deletion(self)" in app
    assert "def _render_document_delete_control" in ui
    assert '"Confirmar eliminacion"' in ui
    assert '_render_document_delete_control(item["path"], item["name"])' in ui
    assert "selected_document_path = options[selected_label]" in ui
    assert "self.vector_store.delete_document(path, wait=True)" in service
    assert "self.knowledge_engine.sync_paths(" in service
    assert "self._delete_ocr_rows(path)" in service
    assert "self.catalog.purge_document(path)" in service
    assert "path.relative_to(library)" in service
