from pathlib import Path
from types import SimpleNamespace

from ai.knowledge_context_builder import (
    KnowledgeContextPackageBuilder,
)


class FakeExtractor:
    def extract(self, path):
        name = Path(path).name
        return SimpleNamespace(
            text=(f"Contenido de {name}. " * 50000),
            method="native_pdf",
            total_pages=30,
        )


def make_builder():
    builder = object.__new__(
        KnowledgeContextPackageBuilder
    )
    builder.extractor = FakeExtractor()
    builder.TASKS = {
        "Análisis de jurisprudencia": "Analizar."
    }
    return builder


def test_two_documents_are_included():
    builder = make_builder()

    package = builder.build_documents_package(
        documents=[
            (Path("tmp1.pdf"), "telecom.pdf"),
            (Path("tmp2.pdf"), "eden.pdf"),
        ],
        objective="Análisis de jurisprudencia",
        instruction="Comparar ambos.",
        document_type="Detección automática",
    )

    assert package.document_count == 2
    assert "## FUENTE 1" in package.content
    assert "## FUENTE 2" in package.content
    assert "Documento: telecom.pdf" in package.content
    assert "Documento: eden.pdf" in package.content


def test_three_documents_are_included():
    builder = make_builder()

    package = builder.build_documents_package(
        documents=[
            (Path("a.pdf"), "a.pdf"),
            (Path("b.pdf"), "b.pdf"),
            (Path("c.pdf"), "c.pdf"),
        ],
    )

    for number, name in enumerate(
        ["a.pdf", "b.pdf", "c.pdf"],
        start=1,
    ):
        assert f"## FUENTE {number}" in package.content
        assert f"Documento: {name}" in package.content


def test_ten_documents_are_included():
    builder = make_builder()
    documents = [
        (Path(f"{number}.pdf"), f"{number}.pdf")
        for number in range(1, 11)
    ]

    package = builder.build_documents_package(
        documents=documents,
    )

    assert package.document_count == 10

    for number in range(1, 11):
        assert f"## FUENTE {number}" in package.content
        assert (
            f"Documento: {number}.pdf"
            in package.content
        )


def test_no_external_helper_dependency():
    builder = make_builder()

    package = builder.build_documents_package(
        documents=[
            (Path("uno.pdf"), "uno.pdf"),
            (Path("dos.pdf"), "dos.pdf"),
        ],
    )

    assert "Trabajá únicamente con los documentos" in package.content
