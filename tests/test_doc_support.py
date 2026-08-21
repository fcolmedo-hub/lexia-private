from pathlib import Path

from docx import Document as DocxDocument

from core.document_detector import DocumentDetector
from core.document_extractor import DocumentExtractor


def test_detector_accepts_doc(tmp_path: Path) -> None:
    source = tmp_path / "Escritos" / "demanda.doc"
    source.parent.mkdir(parents=True)
    source.write_bytes(b"documento binario simulado")

    documents = DocumentDetector(tmp_path).scan()

    assert len(documents) == 1
    assert documents[0].extension == ".doc"
    assert documents[0].category == "Escritos"


def test_extract_doc_uses_temporary_conversion(
    tmp_path: Path,
    monkeypatch,
) -> None:
    source = tmp_path / "prueba.doc"
    source.write_bytes(b"documento binario simulado")

    extractor = DocumentExtractor()

    def fake_convert(
        source_path: Path,
        output_path: Path,
    ) -> None:
        assert source_path == source
        document = DocxDocument()
        document.add_paragraph(
            "Contenido jurídico convertido."
        )
        document.save(output_path)

    monkeypatch.setattr(
        extractor,
        "_convert_doc_to_docx",
        fake_convert,
    )

    result = extractor.extract(source)

    assert result.text == "Contenido jurídico convertido."
    assert result.method == "doc_via_docx"
    assert result.needs_ocr is False
