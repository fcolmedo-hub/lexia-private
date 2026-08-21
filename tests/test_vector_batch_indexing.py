from pathlib import Path
from types import SimpleNamespace

from search.indexer import VectorIndexer


class FakeCatalog:
    def __init__(self, documents):
        self.documents = documents
        self.marked = []

    def pending_vector_relocations(self):
        return []

    def pending_vector_documents(self):
        return self.documents

    def mark_vector_indexed(self, path, content_hash):
        self.marked.append((str(path), content_hash))


class FakeVectorStore:
    def __init__(self):
        self.batches = []

    def replace_documents_batch(self, documents, wait=True):
        self.batches.append([str(d.path) for d in documents])
        return {
            str(d.path.resolve()): len(d.fragments)
            for d in documents
        }

    def delete_document(self, path):
        pass


def make_document(number: int):
    path = Path(f"doc_{number}.txt")
    fragment = SimpleNamespace(text="texto")
    return SimpleNamespace(
        path=path,
        content_hash=f"hash-{number}",
        fragments=[fragment, fragment],
    )


def test_indexer_batches_documents():
    documents = [make_document(i) for i in range(10)]
    catalog = FakeCatalog(documents)
    store = FakeVectorStore()

    result = VectorIndexer(catalog, store).run()

    # El valor predeterminado del Sprint C es 8 documentos por lote.
    assert [len(batch) for batch in store.batches] == [8, 2]
    assert result.documents_indexed == 10
    assert result.fragments_indexed == 20
    assert len(catalog.marked) == 10
