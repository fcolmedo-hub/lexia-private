from pathlib import Path
from core.document_extractor import DocumentExtractor
from core.pipeline import DocumentPipeline
from storage.catalog import DocumentCatalog


def test_incomplete_state_is_not_skippable():
    state = {
        'is_deleted': 0,
        'content_hash': 'abc',
        'text_content': '',
        'extraction_method': '',
        'extraction_error': None,
        'duplicate_of': None,
        'category': 'Sin clasificar',
    }
    assert DocumentPipeline._state_is_complete(state) is False


def test_complete_text_state_is_skippable():
    state = {
        'is_deleted': 0,
        'content_hash': 'abc',
        'text_content': 'Texto jurídico',
        'extraction_method': 'txt',
        'extraction_error': None,
        'duplicate_of': None,
        'category': 'Doctrina',
    }
    assert DocumentPipeline._state_is_complete(state) is True


def test_incomplete_catalog_record_is_reprocessed(tmp_path: Path):
    library = tmp_path / 'data'
    folder = library / 'Doctrina'
    folder.mkdir(parents=True)
    file_path = folder / 'doctrina.txt'
    file_path.write_text('Prescripción tributaria local. ' * 120, encoding='utf-8')
    database = tmp_path / 'catalog.sqlite3'
    first = DocumentPipeline(library, database).run()
    second = DocumentPipeline(library, database).run()
    assert first.new == 1
    assert second.skipped == 1
    catalog = DocumentCatalog(database)
    with catalog._connect() as connection:
        connection.execute(
            "UPDATE documents SET text_content = '', extraction_method = '', extraction_error = NULL WHERE path = ?",
            (str(file_path.resolve()),),
        )
    third = DocumentPipeline(library, database).run()
    assert third.skipped == 0
    assert third.modified == 1


def test_ocr_detection_ignores_isolated_short_page():
    pages = {
        1: 'Texto jurídico suficiente. ' * 40,
        2: 'Texto jurídico suficiente. ' * 40,
        3: 'Texto jurídico suficiente. ' * 40,
        4: '',
    }
    assert DocumentExtractor()._pages_requiring_ocr(pages) == []


def test_ocr_detection_selects_pages_in_scanned_pdf():
    pages = {
        1: 'Texto jurídico suficiente. ' * 40,
        2: '',
        3: '',
        4: '',
    }
    assert DocumentExtractor()._pages_requiring_ocr(pages) == [2, 3, 4]
