from pathlib import Path

from core.document_chunker import DocumentChunker
from models.document import Document


def test_chunker_generates_multiple_fragments() -> None:
    document = Document(
        name="libro.txt",
        path=Path("data/libro.txt"),
        extension=".txt",
        size=5000,
        text=("Argumento jurídico relevante. " * 300).strip(),
    )

    chunker = DocumentChunker(chunk_size=500, overlap=100)
    fragments = chunker.split(document)

    assert len(fragments) > 1
    assert fragments[0].index == 0
    assert fragments[0].document_name == "libro.txt"
    assert fragments[1].start_char < fragments[0].end_char


def test_chunker_returns_empty_list_for_empty_text() -> None:
    document = Document(
        name="vacio.txt",
        path=Path("data/vacio.txt"),
        extension=".txt",
        size=0,
        text="",
    )

    fragments = DocumentChunker().split(document)

    assert fragments == []
