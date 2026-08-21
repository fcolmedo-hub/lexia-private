from pathlib import Path

import services.application as application_module
from search.search_hotfix import SearchHotfixEngine
from storage.catalog import DocumentCatalog


class FakeResult:
    def __init__(self, path, index, score):
        self.document_path = Path(path)
        self.fragment_index = index
        self.score = score


def test_fusion_prioritizes_direct():
    engine = object.__new__(SearchHotfixEngine)
    result = engine._fuse(
        [FakeResult("A.pdf", 0, 2.0)],
        [FakeResult("B.pdf", 0, 1.1)],
        [FakeResult("A.pdf", 0, 0.9), FakeResult("C.pdf", 2, 0.8)],
        10,
    )
    assert [str(item.document_path) for item in result] == ["A.pdf", "B.pdf", "C.pdf"]


def test_direct_document_search_is_functional(tmp_path: Path):
    catalog = DocumentCatalog(tmp_path / "catalog.sqlite3")
    with catalog._connect() as connection:
        connection.execute(
            """
            INSERT INTO documents (
                path, name, category, extension, size, modified_ns,
                content_hash, text_content
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("D:/data/Jurisprudencia/Fallo_CSJN.pdf", "Fallo_CSJN.pdf", "Jurisprudencia", ".pdf", 100, 1, "h1", "texto"),
        )

    rows = catalog.direct_document_search("CSJN")
    assert [row["name"] for row in rows] == ["Fallo_CSJN.pdf"]


def test_application_composes_fast_search_over_hotfix(monkeypatch):
    class FakeCatalogProxy:
        def __init__(self, catalog, root):
            self.catalog = catalog
            self.root = root

    class FakeProfessionalSearch:
        def __init__(self, vector_store, catalog, feedback, history):
            self.vector_store = vector_store
            self.catalog = catalog
            self.feedback = feedback
            self.history = history

    class FakeHotfix:
        def __init__(self, wrapped, catalog):
            self.wrapped = wrapped
            self.catalog = catalog

    class FakeFastSearch:
        def __init__(self, delegate, catalog_proxy):
            self.delegate = delegate
            self.catalog_proxy = catalog_proxy

    monkeypatch.setattr(application_module, "FastSearchCatalogProxy", FakeCatalogProxy)
    monkeypatch.setattr(application_module, "ProfessionalLegalSearchEngine", FakeProfessionalSearch)
    monkeypatch.setattr(application_module, "SearchHotfixEngine", FakeHotfix)
    monkeypatch.setattr(application_module, "FastSearchEngine", FakeFastSearch)

    application = object.__new__(application_module.LexIAApplication)
    application._raw_search = None
    application.catalog = object()
    application._vector_store = object()
    application.feedback = object()
    application.history = object()

    search = application.raw_search
    assert isinstance(search, FakeFastSearch)
    assert isinstance(search.delegate, FakeHotfix)
    assert isinstance(search.delegate.wrapped, FakeProfessionalSearch)
