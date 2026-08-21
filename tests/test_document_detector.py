from pathlib import Path

from core.document_detector import DocumentDetector


def test_detector_infers_category(tmp_path: Path) -> None:
    category = tmp_path / "Jurisprudencia"
    category.mkdir()
    (category / "fallo.txt").write_text(
        "Contenido del fallo.",
        encoding="utf-8",
    )

    documents = DocumentDetector(tmp_path).scan()

    assert len(documents) == 1
    assert documents[0].category == "Jurisprudencia"
