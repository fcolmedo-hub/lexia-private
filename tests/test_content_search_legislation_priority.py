import sqlite3
import sys
from pathlib import Path
import pytest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app/ui2"))

import server  # noqa: E402


def _catalog(path: Path) -> None:
    con = sqlite3.connect(path)
    con.executescript(
        """
        CREATE TABLE documents (
            path TEXT PRIMARY KEY,
            name TEXT,
            category TEXT,
            is_deleted INTEGER DEFAULT 0
        );
        CREATE TABLE fragments (
            document_path TEXT,
            fragment_index INTEGER,
            page_start INTEGER,
            page_end INTEGER
        );
        CREATE VIRTUAL TABLE fragments_fts USING fts5(
            document_path UNINDEXED,
            fragment_index UNINDEXED,
            category UNINDEXED,
            document_name UNINDEXED,
            text_content
        );
        """
    )
    rows = [
        (
            "D:/Biblioteca/Legislación/Santa Fe/Ley 7055.pdf",
            "Ley 7055.pdf",
            "Legislación",
            "Texto preliminar de la norma.\n"
            "artÝculo 5║. Serß procedente el recurso en los casos previstos.\n"
            "ART═CULO 6║. Esta disposici¾n pertenece al artÝculo siguiente.",
        ),
        (
            "D:/Biblioteca/Jurisprudencia/Fallo.pdf",
            "Fallo.pdf",
            "Jurisprudencia",
            "El tribunal analizó el art. 5 de la ley 7055 y confirmó la sentencia.",
        ),
    ]
    for index, (doc_path, name, category, text) in enumerate(rows):
        con.execute(
            "INSERT INTO documents(path,name,category,is_deleted) VALUES(?,?,?,0)",
            (doc_path, name, category),
        )
        con.execute(
            "INSERT INTO fragments(document_path,fragment_index,page_start,page_end) "
            "VALUES(?,?,?,?)",
            (doc_path, 0, index + 1, index + 1),
        )
        con.execute(
            "INSERT INTO fragments_fts(document_path,fragment_index,category,document_name,text_content) "
            "VALUES(?,?,?,?,?)",
            (doc_path, "0", category, name, text),
        )
    con.commit()
    con.close()


def test_detects_law_and_code_article_queries() -> None:
    law = server._legal_citation_intent("art. 970 de la ley 22.415")
    assert law == {
        "article": "970",
        "suffix": "",
        "instrument_kind": "law",
        "instrument": "ley 22415",
        "law_number": "22415",
        "code_name": "",
    }

    code = server._legal_citation_intent(
        "artículo 730 del Código Civil y Comercial"
    )
    assert code["article"] == "730"
    assert code["instrument"] == "codigo civil y comercial"
    assert server._legal_citation_intent(
        "art. 12 del Código de Minería"
    )["instrument"] == "codigo de mineria"
    assert server._legal_citation_intent("prescripción tributaria") is None
    assert server._legal_citation_fts_query(law).startswith('"art"* AND "970"')
    assert '"22 415"' in server._legal_citation_fts_query(law)
    assert server._legal_article_fts_query(law).endswith('AND "970"')
    assert server._legal_citation_document_pattern(law) == "%22415%"
    assert server._legal_citation_document_pattern(code) == "%civil%comercial%"
    assert server._legal_citation_fts_query(code).endswith(
        '"codigo" AND "civil" AND "comercial"'
    )


def test_legislation_article_outranks_judgment_that_quotes_it(
    tmp_path: Path, monkeypatch
) -> None:
    runtime = tmp_path / "runtime"
    runtime.mkdir()
    _catalog(runtime / "lexia_catalog.sqlite3")
    monkeypatch.setattr(server, "RUNTIME_ROOT", runtime)

    result = server._content_search_v2(
        "art. 5 ley 7055",
        limit=2,
    )

    assert result["search_strategy"] == "fts5_legal_citation_priority"
    assert result["legal_citation"] == {
        "article": "5",
        "instrument": "ley 7055",
        "prioritized_category": "Legislación",
    }
    assert result["results"][0]["category"] == "Legislación"
    assert result["results"][0]["legal_article_match"] is True
    assert result["results"][0]["legal_instrument_match"] is True
    assert result["results"][0]["legislation_priority"] is True
    assert result["results"][0]["article_focused"] is True
    assert result["results"][0]["text"].startswith("artÝculo 5║.")
    assert "ART═CULO 6" not in result["results"][0]["text"]


def test_explicit_non_legislation_filter_is_respected(
    tmp_path: Path, monkeypatch
) -> None:
    runtime = tmp_path / "runtime"
    runtime.mkdir()
    _catalog(runtime / "lexia_catalog.sqlite3")
    monkeypatch.setattr(server, "RUNTIME_ROOT", runtime)

    result = server._content_search_v2(
        "art. 5 ley 7055",
        limit=2,
        category="Jurisprudencia",
    )

    assert [row["category"] for row in result["results"]] == ["Jurisprudencia"]
    assert result["legal_citation"]["prioritized_category"] is None

    ordinary = server._content_search_v2("tribunal", limit=2)
    assert ordinary["search_strategy"] == "fts5_match_centered_hybrid"
    assert "legal_citation" not in ordinary
    assert "legislation_priority" not in ordinary["results"][0]


@pytest.mark.parametrize("query,article,suffix,law", [
    ("art. 5 de la ley N°7055", "5", "", "7055"),
    ("Artículo 5º de la Ley Nº 7.055", "5", "", "7055"),
    ("art. 5° bis ley n.º24.240", "5", "bis", "24240"),
    ("art. 1.001 de la ley 48", "1001", "", "48"),
])
def test_number_labels_and_ordinals(query, article, suffix, law):
    intent = server._legal_citation_intent(query)
    assert intent is not None
    assert (intent["article"], intent["suffix"], intent["law_number"]) == (article, suffix, law)


@pytest.mark.parametrize("text", [
    "ARTÍCULO 50. Otro artículo.", "Art. 5 bis. Otro artículo.",
    "Art. 5º bis. Otro artículo.", "Art. 5 ter. Otro artículo.",
    "Art. 5.1. Otro artículo.",
])
def test_article_five_does_not_match_a_different_provision(text):
    intent = server._legal_citation_intent("art. 5 ley 7055")
    assert server._legal_citation_fragment_signals(text, intent)[0] is False
    assert server._legal_article_excerpt(text, intent) == ""


def test_excerpt_prefers_heading_over_an_earlier_cross_reference():
    intent = server._legal_citation_intent("art. 5 ley 7055")
    text = ("Art. 2. Se aplica el art. 5 de esta ley.\n"
            "ARTÍCULO 5º. Este es el contenido solicitado.\n"
            "ARTÍCULO 6. Otra disposición.")
    assert server._legal_article_excerpt(text, intent) == (
        "ARTÍCULO 5º. Este es el contenido solicitado."
    )


def test_direct_law_lookup_survives_missing_fts_article_number(tmp_path, monkeypatch):
    _catalog(tmp_path / "lexia_catalog.sqlite3")
    monkeypatch.setattr(server, "RUNTIME_ROOT", tmp_path)
    with sqlite3.connect(tmp_path / "lexia_catalog.sqlite3") as con:
        con.execute("UPDATE fragments_fts SET text_content=? WHERE category='Legislación'", (
            "ARTÍCULO 5º. Texto solicitado sin número de ley en el cuerpo.\n"
            "ARTÍCULO 6º. Disposición siguiente.",
        ))
    result = server._content_search_v2("art. 5 ley 7055", limit=1)
    first = result["results"][0]
    assert first["document_name"] == "Ley 7055.pdf"
    assert first["text"].startswith("ARTÍCULO 5º.")
    assert "6º" not in first["text"]


def test_other_law_quoting_requested_law_is_not_the_primary_source(tmp_path, monkeypatch):
    _catalog(tmp_path / "lexia_catalog.sqlite3")
    monkeypatch.setattr(server, "RUNTIME_ROOT", tmp_path)
    with sqlite3.connect(tmp_path / "lexia_catalog.sqlite3") as con:
        path = "D:/Biblioteca/Legislación/Ley 9999.pdf"
        con.execute("INSERT INTO documents VALUES(?,?,?,0)", (path, "Ley 9999.pdf", "Legislación"))
        con.execute("INSERT INTO fragments VALUES(?,0,1,1)", (path,))
        con.execute("INSERT INTO fragments_fts VALUES(?,0,?,?,?)", (
            path, "Legislación", "Ley 9999.pdf",
            "Art. 5. Se modifica el art. 5 ley 7055, art. 5 ley 7055.",
        ))
    result = server._content_search_v2("art. 5 ley 7055", limit=1)
    assert result["results"][0]["document_name"] == "Ley 7055.pdf"


def test_law_number_is_not_a_substring_or_unrelated_number():
    intent = server._legal_citation_intent("art. 5 ley 7055")
    assert not server._legal_citation_fragment_signals("Ley 70550", intent)[1]
    assert not server._legal_citation_fragment_signals("Ley 1234, expediente 7055", intent)[1]


def test_bis_is_separate_from_article_without_suffix():
    intent = server._legal_citation_intent("art. 5 bis ley 7055")
    text = "Art. 5. Disposición general.\nArt. 5º bis. Regla especial.\nArt. 6. Otra."
    assert server._legal_article_excerpt(text, intent) == "Art. 5º bis. Regla especial."


def test_pdf_locator_skips_cross_references_and_contents(tmp_path, monkeypatch):
    import fitz
    path = tmp_path / "Ley 7055.pdf"
    with fitz.open() as pdf:
        for text in (
            "El art. 5 de la ley 7055 se menciona en este prologo.",
            "INDICE\nArticulo 5 .............. 4",
            "Articulo 5 bis. Una regla distinta.",
            "Articulo 5. Este es el contenido solicitado.\nArticulo 6. Otra regla.",
        ):
            page = pdf.new_page()
            page.insert_text((72, 180), text)
        pdf.save(path)
    monkeypatch.setattr(server, "_resolve_catalog_document", lambda **kwargs: str(path))
    result = server._legal_article_location(
        str(path), "Articulo 5. Este es el contenido solicitado.", fallback_page=1,
    )
    assert result["found"] is True
    assert result["page"] == 4
    assert result["page_count"] == 4
    assert 140 < result["top"] < 180


def test_pdf_locator_does_not_claim_found_when_pdf_has_only_a_mention(tmp_path, monkeypatch):
    import fitz
    path = tmp_path / "Ley 7055.pdf"
    with fitz.open() as pdf:
        pdf.new_page().insert_text((72, 72), "Esta disposicion remite al art. 5 de la ley.")
        pdf.save(path)
    monkeypatch.setattr(server, "_resolve_catalog_document", lambda **kwargs: str(path))
    assert server._legal_article_location(str(path), "Articulo 5. Texto solicitado.")["found"] is False


def test_category_accent_alias_and_explicit_folder_are_preserved(tmp_path, monkeypatch):
    _catalog(tmp_path / "lexia_catalog.sqlite3")
    monkeypatch.setattr(server, "RUNTIME_ROOT", tmp_path)
    monkeypatch.setattr(server, "_validated_filter_folder", lambda category, folder: folder or "")
    result = server._content_search_v2("art. 5 ley 7055", category="Legislacion", limit=1)
    assert result["results"][0]["document_name"] == "Ley 7055.pdf"
    result = server._content_search_v2(
        "art. 5 ley 7055", category="Legislación", folder="D:/Biblioteca/Legislación/Otra provincia",
    )
    assert result["results"] == []


def test_direct_lookup_reads_catalogued_fragments_even_when_fts_is_stale(tmp_path, monkeypatch):
    _catalog(tmp_path / "lexia_catalog.sqlite3")
    monkeypatch.setattr(server, "RUNTIME_ROOT", tmp_path)
    with sqlite3.connect(tmp_path / "lexia_catalog.sqlite3") as con:
        con.execute("ALTER TABLE fragments ADD COLUMN text_content TEXT")
        con.execute("UPDATE fragments SET text_content=? WHERE document_path LIKE '%7055%'", (
            "ARTICULO 5º. El artículo está en el catálogo aunque FTS esté desactualizado.",
        ))
        con.execute("UPDATE fragments_fts SET text_content='Texto anterior' WHERE category='Legislación'")
    result = server._content_search_v2("art. 5 ley 7055", limit=1)
    assert result["results"][0]["document_name"] == "Ley 7055.pdf"
    assert "desactualizado" in result["results"][0]["text"]
