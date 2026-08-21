from pathlib import Path

from ai.intelligent_context_selector import IntelligentContextSelector


class FakeResult:
    def __init__(self, path, index, category, text):
        self.document_path = Path(path)
        self.fragment_index = index
        self.category = category
        self.text = text


def ranked(result, score=1.0):
    return (score, result, ["concepto"], "")


def test_prefers_distinct_documents():
    selector = IntelligentContextSelector()
    items = [
        ranked(FakeResult("A.pdf", 0, "Jurisprudencia", "texto alfa")),
        ranked(FakeResult("A.pdf", 3, "Jurisprudencia", "texto beta")),
        ranked(FakeResult("B.pdf", 0, "Doctrina", "texto gamma")),
        ranked(FakeResult("C.pdf", 0, "Normativa", "texto delta")),
    ]
    selected = selector.select(items, 3)
    paths = [str(item[1].document_path) for item in selected]
    assert paths == ["A.pdf", "B.pdf", "C.pdf"]


def test_skips_near_duplicate_text():
    selector = IntelligentContextSelector(similarity_threshold=0.70)
    repeated = (
        "recurso extraordinario tribunal fiscal "
        "plazo razonable sentencia federal"
    )
    items = [
        ranked(FakeResult("A.pdf", 0, "Jurisprudencia", repeated)),
        ranked(FakeResult("B.pdf", 0, "Jurisprudencia", repeated)),
        ranked(FakeResult("C.pdf", 0, "Doctrina", "doctrina tributaria distinta")),
    ]
    selected = selector.select(items, 2)
    paths = {str(item[1].document_path) for item in selected}
    assert "A.pdf" in paths
    assert "B.pdf" not in paths


def test_avoids_adjacent_fragments():
    selector = IntelligentContextSelector(max_per_document=2)
    items = [
        ranked(FakeResult("A.pdf", 3, "Jurisprudencia", "uno dos tres")),
        ranked(FakeResult("A.pdf", 4, "Jurisprudencia", "cuatro cinco seis")),
        ranked(FakeResult("A.pdf", 7, "Jurisprudencia", "siete ocho nueve")),
    ]
    selected = selector.select(items, 2)
    indexes = [item[1].fragment_index for item in selected]
    assert indexes == [3, 7]


def test_builder_was_patched():
    source = Path("ai/knowledge_context_builder.py").read_text(
        encoding="utf-8"
    )
    assert "IntelligentContextSelector" in source
    assert "context_intelligent_selection" in source
