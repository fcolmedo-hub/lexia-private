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


def test_all_selected_documents_are_included():
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
    assert package.content.index(
        "Documento: telecom.pdf"
    ) < package.content.index(
        "Documento: eden.pdf"
    )


def test_large_first_document_does_not_hide_second():
    builder = make_builder()

    package = builder.build_documents_package(
        documents=[
            (Path("grande.pdf"), "grande.pdf"),
            (Path("segundo.pdf"), "segundo.pdf"),
            (Path("tercero.pdf"), "tercero.pdf"),
        ],
    )

    assert "[FUENTE 1]" in package.content
    assert "[FUENTE 2]" in package.content
    assert "[FUENTE 3]" in package.content
    assert "Documento: segundo.pdf" in package.content
    assert "Documento: tercero.pdf" in package.content
