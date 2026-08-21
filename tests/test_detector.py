from core.document_detector import DocumentDetector


def test_detector_creates_missing_library(tmp_path):
    library_path = tmp_path / "data"
    detector = DocumentDetector(library_path)

    documents = detector.scan()

    assert library_path.exists()
    assert documents == []
