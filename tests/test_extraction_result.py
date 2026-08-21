from core.document_extractor import ExtractionResult


def test_extraction_result_tracks_ocr() -> None:
    result = ExtractionResult(
        text="Texto",
        method="hybrid_pdf",
        total_pages=10,
        ocr_pages=2,
    )

    assert result.method == "hybrid_pdf"
    assert result.ocr_pages == 2
