from services.knowledge_engine import KnowledgeEngine


class _DuplicateRepository:
    def __init__(self):
        self.removed = []

    def knowledge_for_path(self, _path):
        return None

    def remove_path(self, path):
        self.removed.append(path)
        raise AssertionError("No debe intentar borrar del Knowledge Engine un duplicado no indexado")


def test_deleted_duplicate_absent_from_knowledge_is_not_an_error():
    engine = KnowledgeEngine.__new__(KnowledgeEngine)
    engine.repository = _DuplicateRepository()

    result = engine.sync_paths([], deleted_paths=["D:/LexIA/Jurisprudencia/duplicado.pdf"])

    assert result.examined == 1
    assert result.skipped == 1
    assert result.removed == 0
    assert result.errors == 0
    assert engine.repository.removed == []
