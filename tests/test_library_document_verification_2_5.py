from pathlib import Path


def test_library_document_verification_is_unified_and_lazy():
    ui = (
        Path(__file__).parents[1] / "app" / "ui.py"
    ).read_text(encoding="utf-8")

    assert 'library_mode = "Documentos"' in ui
    assert '"Vista de biblioteca"' not in ui
    assert 'key=f"library_verify_document_{token}"' in ui
    assert "app.document_inspector.inspect(path_text)" in ui
    assert "def _render_document_inspection(inspection)" in ui
    assert "library_inspection_path" in ui
    assert '"Cerrar verificación"' in ui
    assert "library_folder_multiselect" in ui
    assert "library_documents_filter_form" in ui
