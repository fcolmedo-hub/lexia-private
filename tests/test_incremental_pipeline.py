from pathlib import Path

from core.pipeline import DocumentPipeline


def test_second_run_skips_unchanged_document(tmp_path: Path) -> None:
    library = tmp_path / "data"
    folder = library / "Jurisprudencia"
    folder.mkdir(parents=True)
    (folder / "fallo.txt").write_text(
        "Fundamento jurídico. " * 200,
        encoding="utf-8",
    )
    database = tmp_path / "catalog.sqlite3"

    first = DocumentPipeline(library, database).run()
    second = DocumentPipeline(library, database).run()

    assert first.new == 1
    assert first.skipped == 0
    assert second.new == 0
    assert second.skipped == 1
