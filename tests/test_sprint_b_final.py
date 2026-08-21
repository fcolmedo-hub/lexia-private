from pathlib import Path

from core.pipeline import DocumentPipeline
from storage.catalog import DocumentCatalog


def test_catalog_file_state_contains_processing_fields(tmp_path: Path) -> None:
    library = tmp_path / "data"
    folder = library / "Jurisprudencia"
    folder.mkdir(parents=True)
    file_path = folder / "fallo.txt"
    file_path.write_text("Fundamento jurídico. " * 100, encoding="utf-8")
    database = tmp_path / "catalog.sqlite3"
    result = DocumentPipeline(library, database).run()
    assert result.new == 1
    state = DocumentCatalog(database).get_file_state(file_path)
    assert state is not None
    assert "text_content" in state
    assert "extraction_error" in state
    assert "extraction_method" in state
    assert "category" in state
    assert state["text_content"]


def test_valid_document_is_skipped_but_incomplete_is_reprocessed(tmp_path: Path) -> None:
    library = tmp_path / "data"
    folder = library / "Doctrina"
    folder.mkdir(parents=True)
    file_path = folder / "doctrina.txt"
    file_path.write_text("Prescripción tributaria local. " * 120, encoding="utf-8")
    database = tmp_path / "catalog.sqlite3"
    first = DocumentPipeline(library, database).run()
    second = DocumentPipeline(library, database).run()
    assert first.new == 1
    assert second.skipped == 1
    assert second.modified == 0
    catalog = DocumentCatalog(database)
    with catalog._connect() as connection:
        connection.execute("""
            UPDATE documents
            SET text_content = '', extraction_method = '', extraction_error = NULL
            WHERE path = ?
        """, (str(file_path.resolve()),))
    third = DocumentPipeline(library, database).run()
    assert third.skipped == 0
    assert third.modified == 1
    assert third.failed == 0
    repaired = catalog.get_file_state(file_path)
    assert repaired is not None
    assert repaired["text_content"]
    assert repaired["extraction_method"] == "txt"
