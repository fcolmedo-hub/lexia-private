from core.document_extractor import DocumentExtractor


class _OCRText:
    def extract_pdf_pages(self, _path, pages, **_kwargs):
        return {
            page: "Texto OCR legible aunque sea más corto."
            for page in pages
        }


def test_native_pdf_with_one_short_page_does_not_require_ocr() -> None:
    extractor = DocumentExtractor()
    pages = {
        1: "Texto jurídico suficiente. " * 40,
        2: "Texto jurídico suficiente. " * 40,
        3: "Texto jurídico suficiente. " * 40,
        4: "",
    }
    assert extractor._pages_requiring_ocr(pages) == []


def test_mostly_scanned_pdf_requires_only_empty_pages() -> None:
    extractor = DocumentExtractor()
    pages = {
        1: "Texto jurídico suficiente. " * 40,
        2: "",
        3: "",
        4: "",
    }
    assert extractor._pages_requiring_ocr(pages) == [2, 3, 4]


def test_fully_native_pdf_does_not_require_ocr() -> None:
    extractor = DocumentExtractor()
    pages = {
        1: "Texto jurídico suficiente. " * 30,
        2: "Texto jurídico suficiente. " * 30,
        3: "Texto jurídico suficiente. " * 30,
    }
    assert extractor._pages_requiring_ocr(pages) == []


def test_corrupted_pdf_text_layer_requires_ocr_even_when_it_is_long() -> None:
    extractor = DocumentExtractor()
    pages = {
        1: "□" * 700,
        2: "Texto jurídico suficiente. " * 30,
    }
    assert extractor._pages_requiring_ocr(pages) == [1]


def test_ocr_replaces_longer_corrupted_native_text(monkeypatch, tmp_path) -> None:
    extractor = DocumentExtractor(ocr_service=_OCRText())
    monkeypatch.setattr(extractor, "_extract_pdf_native", lambda _path: {1: "□" * 700})
    result = extractor._extract_pdf(tmp_path / "ilegible.pdf", allow_ocr=True)
    assert result.text == "--- PÁGINA 1 ---\nTexto OCR legible aunque sea más corto."
    assert result.method == "ocr_pdf"


def test_manual_ocr_renders_visible_vector_pages_without_embedded_images(
    monkeypatch, tmp_path
) -> None:
    extractor = DocumentExtractor(ocr_service=_OCRText())
    monkeypatch.setattr(extractor, "_extract_pdf_native", lambda _path: {1: ""})
    monkeypatch.setattr(extractor, "_image_pages_with_content", lambda *_args: [])

    result = extractor._extract_pdf(
        tmp_path / "vectorial.pdf",
        allow_ocr=True,
        force_ocr_pages=True,
    )

    assert result.text == "--- PÁGINA 1 ---\nTexto OCR legible aunque sea más corto."
    assert result.ocr_pages == 1
