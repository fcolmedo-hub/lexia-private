from knowledge.extractor import DeterministicKnowledgeExtractor
from knowledge.repository import KnowledgeRepository


def test_extracts_administrative_concepts():
    extractor = DeterministicKnowledgeExtractor()
    document = extractor.extract(
        "fallo.pdf", "hash", "fallo", "Jurisprudencia",
        "El acto administrativo carece de motivación y competencia administrativa.",
    )
    assert "Acto administrativo" in document.concepts
    assert "Motivación" in document.concepts


def test_repository_roundtrip(tmp_path):
    repository = KnowledgeRepository(tmp_path / "knowledge.sqlite3")
    extractor = DeterministicKnowledgeExtractor()
    document = extractor.extract(
        "mutual.pdf", "hash", "mutual", "Doctrina",
        "Ley 20.321. Asociación mutual sin fines de lucro. Exención de ingresos brutos.",
    )
    repository.save(document)
    saved = repository.knowledge_for_path("mutual.pdf")
    assert "Mutuales" in saved["concepts"]
