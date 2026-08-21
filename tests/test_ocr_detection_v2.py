from core.document_extractor import DocumentExtractor


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
