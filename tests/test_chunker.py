from pathlib import Path

from core.document_chunker import DocumentChunker
from models.document import Document


def test_chunker_keeps_document_reference() -> None:
    document = Document(
        name="libro.txt",
        path=Path("data/Doctrina/libro.txt"),
        category="Doctrina",
        extension=".txt",
        size=1000,
        modified_ns=1,
        text=("Responsabilidad del Estado. " * 200),
    )

    fragments = DocumentChunker(
        chunk_size=500,
        overlap=100,
    ).split(document)

    assert len(fragments) > 1
    assert all(
        fragment.category == "Doctrina"
        for fragment in fragments
    )
    assert fragments[1].start_char < fragments[0].end_char
