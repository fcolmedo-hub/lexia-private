from pathlib import Path

from core.document_extractor import DocumentExtractor


def test_extract_txt(tmp_path: Path) -> None:
    file_path = tmp_path / "prueba.txt"
    file_path.write_text("Contenido jurídico de prueba.", encoding="utf-8")

    result = DocumentExtractor().extract(file_path)

    assert result.text == "Contenido jurídico de prueba."
    assert result.method == "txt"
    assert result.needs_ocr is False
