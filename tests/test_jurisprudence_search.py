import json

from app.ui2.jurisprudence_search import metadata_bonus, parse_filter_envelope


def _envelope(payload):
    raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    return "LEXIAJURISX" + raw.hex()


def test_filter_envelope_transports_query_and_filters():
    query, filters = parse_filter_envelope(_envelope({
        "text_query": "prescripción tributaria",
        "court": "Corte Suprema",
        "province": "Santa Fe",
        "scope": "Provincial",
    }))
    assert query == "prescripción tributaria"
    assert filters == {
        "court": "Corte Suprema",
        "province": "Santa Fe",
        "scope": "Provincial",
    }


def test_filter_envelope_keeps_visible_query_when_present():
    query, filters = parse_filter_envelope(
        "plazo razonable " + _envelope({"text_query": "ignorar", "chamber": "Sala B"})
    )
    assert query == "plazo razonable"
    assert filters == {"chamber": "Sala B"}


def test_metadata_bonus_is_capped_and_requires_matches():
    metadata = {
        "court": "Corte Suprema de Justicia de la Nación",
        "case_title": "Municipalidad c/ Empresa",
        "laws": ["Ley 11.683"],
        "articles": ["art. 18"],
    }
    assert metadata_bonus(metadata, "término inexistente") == 0.0
    bonus = metadata_bonus(metadata, "Corte Suprema Ley 11683 Municipalidad")
    assert 0.0 < bonus <= 10.0
