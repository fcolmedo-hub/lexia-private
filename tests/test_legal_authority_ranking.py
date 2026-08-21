from pathlib import Path

from ai.legal_authority_ranker import LegalAuthorityRanker


class FakeResult:
    def __init__(self, name, category, metadata):
        self.document_name = name
        self.document_path = Path(name)
        self.category = category
        self.metadata = metadata


class FakePlan:
    preferred_authorities = ["Corte Suprema"]
    jurisdictions = ["Nacional/Federal"]


def item(score, result):
    return (score, result, ["concepto"], "")


def test_csjn_outranks_lower_court_with_close_base_score():
    ranker = LegalAuthorityRanker()

    lower = FakeResult(
        "a.pdf",
        "Jurisprudencia",
        {
            "court": "Juzgado Federal",
            "jurisdiction": "Nacional/Federal",
            "date": "2025-01-01",
        },
    )
    csjn = FakeResult(
        "b.pdf",
        "Jurisprudencia",
        {
            "court": "Corte Suprema de Justicia de la Nación",
            "jurisdiction": "Nacional/Federal",
            "date": "2020-01-01",
        },
    )

    ranked = ranker.rerank(
        [
            item(0.90, lower),
            item(0.82, csjn),
        ],
        FakePlan(),
    )

    assert ranked[0][1].document_name == "b.pdf"


def test_category_bonus_does_not_destroy_base_relevance():
    ranker = LegalAuthorityRanker()

    strong = FakeResult("strong.pdf", "Escritos", {})
    weak = FakeResult("weak.pdf", "Jurisprudencia", {})

    ranked = ranker.rerank(
        [
            item(1.00, strong),
            item(0.50, weak),
        ],
        None,
    )

    assert ranked[0][1].document_name == "strong.pdf"


def test_builder_has_legal_authority_stage():
    source = Path(
        "ai/knowledge_context_builder.py"
    ).read_text(encoding="utf-8")

    assert "LegalAuthorityRanker" in source
    assert "legal_authority_ranking" in source
