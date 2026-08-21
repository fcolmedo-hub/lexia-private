from core.pipeline import DocumentPipeline


def test_incomplete_state_is_not_skippable() -> None:
    state = {
        "is_deleted": 0,
        "size": 100,
        "modified_ns": 123,
        "content_hash": "abc",
        "text_content": "",
        "extraction_method": "",
        "extraction_error": None,
        "duplicate_of": None,
        "category": "Sin clasificar",
    }

    assert DocumentPipeline._state_is_complete(state) is False


def test_failed_state_is_not_skippable() -> None:
    state = {
        "is_deleted": 0,
        "content_hash": "abc",
        "text_content": "",
        "extraction_method": "doc_via_docx",
        "extraction_error": "falló la extracción",
        "duplicate_of": None,
        "category": "Sin clasificar",
    }

    assert DocumentPipeline._state_is_complete(state) is False


def test_complete_text_state_is_skippable() -> None:
    state = {
        "is_deleted": 0,
        "content_hash": "abc",
        "text_content": "Texto jurídico",
        "extraction_method": "doc_via_docx",
        "extraction_error": None,
        "duplicate_of": None,
        "category": "Doctrina",
    }

    assert DocumentPipeline._state_is_complete(state) is True


def test_duplicate_state_is_skippable() -> None:
    state = {
        "is_deleted": 0,
        "content_hash": "abc",
        "text_content": "",
        "extraction_method": "duplicate",
        "extraction_error": None,
        "duplicate_of": "D:/original.doc",
        "category": "Sin clasificar",
    }

    assert DocumentPipeline._state_is_complete(state) is True
