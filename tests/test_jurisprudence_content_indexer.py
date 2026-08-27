from storage.jurisprudence_content_indexer import (
    _parse_parties,
    _safe_metadata_title,
    _split_values,
    _topics_from_metadata,
)


def test_safe_case_title_and_parties():
    title = "Municipalidad de Rosario c/ Nestlé Argentina S.A. s/ apremio"
    assert _safe_metadata_title(title) == title
    assert _parse_parties(title) == (
        "Municipalidad de Rosario",
        "Nestlé Argentina S.A.",
    )


def test_narrative_title_is_rejected():
    assert _safe_metadata_title(
        "Interpone la actora Empresa S.A. la presente acción contra AFIP"
    ) == ""


def test_laws_and_articles_split_and_deduplicate():
    assert _split_values("Ley 11.683 | Ley 23.548 | Ley 11.683") == [
        "Ley 11.683",
        "Ley 23.548",
    ]
    assert _split_values("art. 14; art. 18") == ["art. 14", "art. 18"]


def test_topics_only_from_explicit_metadata():
    assert _topics_from_metadata({"voces": "prescripción | tributos locales"}) == [
        "prescripción",
        "tributos locales",
    ]
    assert _topics_from_metadata({"title": "un fallo"}) == []
