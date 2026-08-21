from pathlib import Path
from services.knowledge_engine import KnowledgeEngine

class FakeRepository:
    def __init__(self):
        self.moves = []
    def move_path(self, old_path, new_path):
        self.moves.append((old_path, new_path))
        return 1

def test_knowledge_move_document_uses_repository(tmp_path: Path):
    engine = object.__new__(KnowledgeEngine)
    engine.repository = FakeRepository()
    old_path = tmp_path / "A.pdf"
    new_path = tmp_path / "sub" / "A.pdf"
    assert engine.move_document(old_path, new_path) == 1
    assert engine.repository.moves == [
        (str(old_path.resolve()), str(new_path.resolve()))
    ]

def test_autosync_keeps_moves_separate():
    source = Path("services/autosync_service.py").read_text(encoding="utf-8")
    assert "_moved_files" in source
    assert "move_successes" in source
    assert "affected_paths -= moved_paths" in source
    assert "rebuild_relations=False" in source
