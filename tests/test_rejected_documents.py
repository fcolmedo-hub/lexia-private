from pathlib import Path

from services.rejected_document_service import RejectedDocumentService


def test_html_named_pdf_is_quarantined(tmp_path: Path):
    library = tmp_path / "data"
    library.mkdir()
    source = library / "error.pdf"
    source.write_text("<html><body>Error</body></html>", encoding="utf-8")
    service = RejectedDocumentService(tmp_path / "Rejected Documents")
    result = service.inspect_and_quarantine(source)
    assert result is not None
    assert result.category == "HTML o XML"
    assert not source.exists()
    assert result.destination_path.exists()
    assert service.log_path.exists()


def test_valid_pdf_is_never_quarantined(tmp_path: Path):
    import fitz
    source = tmp_path / "valido.pdf"
    document = fitz.open()
    document.new_page()
    document.save(source)
    document.close()
    service = RejectedDocumentService(tmp_path / "Rejected Documents")
    result = service.inspect_and_quarantine(source)
    assert result is None
    assert source.exists()
    assert not service.root_path.exists()


def test_empty_file_is_quarantined(tmp_path: Path):
    source = tmp_path / "vacio.pdf"
    source.write_bytes(b"")
    service = RejectedDocumentService(tmp_path / "Rejected Documents")
    result = service.inspect_and_quarantine(source)
    assert result is not None
    assert result.category == "Vacíos"
    assert not source.exists()


def test_rejected_folder_is_outside_library(tmp_path: Path):
    library = tmp_path / "data"
    rejected = tmp_path / "Rejected Documents"
    assert rejected.parent == library.parent
    assert rejected != library
    assert library not in rejected.parents
