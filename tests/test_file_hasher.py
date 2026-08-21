from pathlib import Path

from core.file_hasher import FileHasher


def test_hash_changes_when_content_changes(tmp_path: Path) -> None:
    path = tmp_path / "documento.txt"
    path.write_text("texto uno", encoding="utf-8")
    first = FileHasher().calculate(path)
    path.write_text("texto dos", encoding="utf-8")
    second = FileHasher().calculate(path)
    assert first != second
