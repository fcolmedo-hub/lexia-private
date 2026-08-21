from pathlib import Path
from types import SimpleNamespace

from ai.knowledge_context_builder import (
    KnowledgeContextPackageBuilder,
)


class FakeExtractor:
    def extract(self, path):
        return SimpleNamespace(
            text=f"Contenido de {Path(path).name}",
            method="txt",
            total_pages=1,
        )


def test_build_documents_package():
    builder = object.__new__(
        KnowledgeContextPackageBuilder
    )
    builder.extractor = FakeExtractor()
    builder.TASKS = {
        "Análisis de jurisprudencia": "Analizar."
    }
    builder.BASE_INSTRUCTIONS = "Trabajá con las fuentes."

    package = builder.build_documents_package(
        documents=[
            (Path("temporal1.txt"), "primero.txt"),
            (Path("temporal2.txt"), "segundo.txt"),
        ],
        objective="Análisis de jurisprudencia",
        instruction="Comparar ambos.",
        document_type="Detección automática",
    )

    assert package.document_count == 2
    assert "[FUENTE 1]" in package.content
    assert "[FUENTE 2]" in package.content
    assert "primero.txt" in package.content
    assert "segundo.txt" in package.content
    assert "Comparar ambos." in package.content
