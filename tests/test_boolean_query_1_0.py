import pytest

from search.boolean_query import (
    BooleanQuerySyntaxError,
    parse_boolean_query,
)


def test_normal_query_keeps_current_mode():
    q = parse_boolean_query("plazo razonable")

    assert q.explicit is False
    assert q.fts_query == ""
    assert q.semantic_text == "plazo razonable"


def test_and():
    q = parse_boolean_query("aduana AND importación")

    assert q.explicit is True
    assert q.fts_query == '"aduana" AND "importación"'


def test_or():
    q = parse_boolean_query("prescripción OR caducidad")

    assert q.fts_query == '"prescripción" OR "caducidad"'


def test_not():
    q = parse_boolean_query("aduana NOT contrabando")

    assert q.fts_query == '"aduana" NOT "contrabando"'


def test_quoted_phrases_and_parentheses():
    q = parse_boolean_query(
        '("solve et repete" OR "pago previo") '
        "AND constitucionalidad"
    )

    assert q.fts_query == (
        '( "solve et repete" OR "pago previo" ) '
        'AND "constitucionalidad"'
    )


def test_complex_legal_query():
    q = parse_boolean_query(
        '("artículo 970" OR "art. 970") '
        "AND importación NOT contrabando"
    )

    assert q.fts_query == (
        '( "artículo 970" OR "art. 970" ) '
        'AND "importación" NOT "contrabando"'
    )


@pytest.mark.parametrize(
    "query",
    [
        "aduana AND",
        "AND aduana",
        "aduana OR OR importación",
        "(aduana AND importación",
        "aduana AND importación)",
        "aduana AND (OR importación)",
    ],
)
def test_invalid_syntax(query):
    with pytest.raises(BooleanQuerySyntaxError):
        parse_boolean_query(query)
