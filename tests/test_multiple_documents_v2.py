from pathlib import Path
from types import SimpleNamespace
from ai.knowledge_context_builder import KnowledgeContextPackageBuilder

class FakeExtractor:
    def extract(self, path):
        return SimpleNamespace(
            text=f"Contenido de {Path(path).name}",
            method="txt",
            total_pages=1,
        )

def test_multiple_documents_v2():
    builder = object.__new__(KnowledgeContextPackageBuilder)
    builder.extractor = FakeExtractor()
    builder.TASKS = {"Análisis de jurisprudencia": "Analizar."}

    package = builder.build_documents_package(
        documents=[
            (Path("uno.txt"), "primero.txt"),
            (Path("dos.txt"), "segundo.txt"),
        ],
        objective="Análisis de jurisprudencia",
        instruction="Comparar ambos.",
        document_type="Detección automática",
    )

    assert package.document_count == 2
    assert "[FUENTE 1]" in package.content
    assert "[FUENTE 2]" in package.content
    assert "Trabajá únicamente con los documentos" in package.content
