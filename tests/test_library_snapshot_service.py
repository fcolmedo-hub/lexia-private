from pathlib import Path

from services.library_snapshot_service import (
    LibrarySnapshotService,
)


def test_snapshot_detects_new_modified_and_deleted(
    tmp_path: Path,
) -> None:
    library = tmp_path / "data"
    library.mkdir()
    snapshot_path = tmp_path / "snapshot.json"

    service = LibrarySnapshotService(
        library,
        snapshot_path,
        {".pdf", ".doc", ".docx", ".txt"},
    )

    first = library / "uno.txt"
    first.write_text("primero", encoding="utf-8")

    changed, deleted, snapshot = service.scan()

    assert str(first.resolve()) in changed
    assert deleted == set()

    service.save(snapshot)

    changed, deleted, snapshot = service.scan()

    assert changed == set()
    assert deleted == set()

    first.write_text(
        "contenido modificado",
        encoding="utf-8",
    )
    second = library / "dos.pdf"
    second.write_bytes(b"%PDF-simulado")

    changed, deleted, snapshot = service.scan()

    assert str(first.resolve()) in changed
    assert str(second.resolve()) in changed
    assert deleted == set()

    service.save(snapshot)
    first.unlink()

    changed, deleted, snapshot = service.scan()

    assert str(first.resolve()) in deleted
    assert str(second.resolve()) not in changed


def test_snapshot_ignores_unsupported_files(
    tmp_path: Path,
) -> None:
    library = tmp_path / "data"
    library.mkdir()

    service = LibrarySnapshotService(
        library,
        tmp_path / "snapshot.json",
        {".pdf", ".doc", ".docx", ".txt"},
    )

    (library / "imagen.jpg").write_bytes(b"jpg")
    changed, deleted, snapshot = service.scan()

    assert changed == set()
    assert deleted == set()
    assert snapshot == {}
