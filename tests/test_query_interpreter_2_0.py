from pathlib import Path

from ai.legal_query_expander import LegalQueryExpander


def test_expands_plazo_razonable():
    expander = LegalQueryExpander()
    queries = expander.expand(
        "plazo razonable",
        [],
        10,
    )

    assert "plazo razonable" in queries
    assert any(
        "Convención Americana" in value
        for value in queries
    )
    assert any(
        "demora judicial" in value
        for value in queries
    )


def test_does_not_expand_unrelated_query():
    expander = LegalQueryExpander()
    queries = expander.expand(
        "contrato de locación rural",
        [],
        10,
    )

    assert queries == ["contrato de locación rural"]


def test_deduplicates_existing_queries():
    expander = LegalQueryExpander()
    queries = expander.expand(
        "recurso extraordinario",
        ["recurso extraordinario federal"],
        10,
    )

    assert (
        queries.count("recurso extraordinario federal")
        == 1
    )


def test_builder_has_query_expansion_stage():
    source = Path(
        "ai/knowledge_context_builder.py"
    ).read_text(encoding="utf-8")

    assert "LegalQueryExpander" in source
    assert "query_expansion_2_0" in source
