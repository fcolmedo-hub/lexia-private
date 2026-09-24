from core.document_extractor import DocumentExtractor
from config.settings import SETTINGS


class RecordingOCR:
    def __init__(self):
        self.calls = []

    def extract_pdf_pages(self, _path, pages, *, progress_callback, total_pages):
        self.calls.append((list(pages), total_pages))
        if progress_callback:
            progress_callback(pages[-1], total_pages)
        return {page: f"Texto reconocido en la página {page}." for page in pages}


def test_scanned_pdf_larger_than_ocr_batch_keeps_every_page(monkeypatch, tmp_path):
    batch_size = SETTINGS.ocr_max_pages_per_document
    page_count = batch_size + 5
    extractor = DocumentExtractor(ocr_service=RecordingOCR())
    monkeypatch.setattr(extractor, "_extract_pdf_native", lambda _path: dict.fromkeys(range(1, page_count + 1), ""))
    monkeypatch.setattr(
        extractor,
        "_pages_requiring_ocr",
        lambda _path, _pages, *, force_short_pages: list(range(1, page_count + 1)),
    )
    progress = []

    result = extractor._extract_pdf(
        tmp_path / "expediente.pdf", allow_ocr=True,
        progress_callback=lambda page, total: progress.append((page, total)),
    )

    assert [len(pages) for pages, _ in extractor.ocr_service.calls] == [batch_size, 5]
    assert all(total == page_count for _, total in extractor.ocr_service.calls)
    assert progress == [(batch_size, page_count), (page_count, page_count)]
    assert result.total_pages == page_count
    assert result.ocr_pages == page_count
    assert result.method == "ocr_pdf"
    assert f"--- PÁGINA {page_count} ---" in result.text


def test_long_hybrid_pdf_only_sends_unreadable_page_to_ocr(monkeypatch, tmp_path):
    page_count = SETTINGS.ocr_max_pages_per_document + 1
    extractor = DocumentExtractor(ocr_service=RecordingOCR())
    pages = {page: "Texto nativo suficiente. " * 10 for page in range(1, page_count + 1)}
    pages[page_count] = ""
    monkeypatch.setattr(extractor, "_extract_pdf_native", lambda _path: pages)
    monkeypatch.setattr(
        extractor, "_pages_requiring_ocr",
        lambda _path, _pages, *, force_short_pages: [page_count],
    )

    result = extractor._extract_pdf(tmp_path / "expediente.pdf", allow_ocr=True)

    assert extractor.ocr_service.calls == [([page_count], page_count)]
    assert result.method == "hybrid_pdf"
    assert result.ocr_pages == 1
    assert f"--- PÁGINA {page_count} ---" in result.text
