from pathlib import Path

from core.document_extractor import DocumentExtractor


def test_blank_page_ocr_guard_uses_actual_page_decision(
    tmp_path: Path,
    monkeypatch,
) -> None:
    extractor = DocumentExtractor()

    assert extractor._pages_requiring_ocr(
        {1: "Texto jurídico " * 10, 2: "Fundamento " * 10}
    ) == []

    assert extractor._pages_requiring_ocr(
        {1: "Texto jurídico " * 10, 2: "nota", 3: "Fundamento " * 10}
    ) == []

    pdf_path = tmp_path / "documento.pdf"
    monkeypatch.setattr(
        extractor,
        "_image_pages_with_content",
        lambda path, candidates: [],
    )
    assert extractor._pages_requiring_ocr(pdf_path, {1: "", 2: ""}) == []

    monkeypatch.setattr(
        extractor,
        "_image_pages_with_content",
        lambda path, candidates: list(candidates),
    )
    assert extractor._pages_requiring_ocr(pdf_path, {1: "", 2: ""}) == [1, 2]
