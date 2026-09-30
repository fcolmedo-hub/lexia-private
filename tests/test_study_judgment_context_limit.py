from pathlib import Path

from ai import knowledge_context_builder as module
from config.settings import SETTINGS


class CatalogWithJudgment:
    def __init__(self, _path):
        pass

    def get_file_state(self, _path):
        return {
            "text_content": "A" * 250000,
            "is_deleted": 0,
            "extraction_method": "ocr",
            "total_pages": 110,
        }


def test_study_uses_its_own_larger_budget(monkeypatch):
    monkeypatch.setattr(module, "DocumentCatalog", CatalogWithJudgment)
    builder = object.__new__(module.KnowledgeContextPackageBuilder)
    package = builder.build_documents_package(
        documents=[(Path("fallo.pdf"), "fallo.pdf")],
        objective="Análisis de jurisprudencia",
        document_type="Fallo judicial",
    )

    source = package.content.split("Contenido:\n", 1)[1]
    assert source.startswith("A" * SETTINGS.context_builder_study_max_chars_per_document)
    assert source[SETTINGS.context_builder_study_max_chars_per_document] == "\n"
    assert "[CONTENIDO TRUNCADO POR LÍMITE DEL CONTEXTO]" in source
    assert "Páginas detectadas: 110" in package.content
    assert package.interpretation["source_lengths"] == [{
        "document": "fallo.pdf", "available": 250000, "included": 200000,
    }]
    assert SETTINGS.context_builder_max_total_chars == 52000
