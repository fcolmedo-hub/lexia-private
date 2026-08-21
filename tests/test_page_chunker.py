from pathlib import Path

from core.document_chunker import DocumentChunker
from models.document import Document


def test_chunker_detects_page_numbers() -> None:
    text = (
        "--- PÁGINA 1 ---\n"
        + ("Fundamento uno. " * 80)
        + "\n--- PÁGINA 2 ---\n"
        + ("Fundamento dos. " * 80)
    )

    document = Document(
        name="fallo.pdf",
        path=Path("data/Jurisprudencia/fallo.pdf"),
        category="Jurisprudencia",
        extension=".pdf",
        size=1000,
        modified_ns=1,
        text=text,
    )

    fragments = DocumentChunker(
        chunk_size=700,
        overlap=100,
    ).split(document)

    assert fragments
    assert fragments[0].page_start == 1
    assert any(fragment.page_end == 2 for fragment in fragments)
