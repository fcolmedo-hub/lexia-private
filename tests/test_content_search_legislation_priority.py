import sqlite3
import sys
from pathlib import Path


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
    # Reproduce the real Ley 7055 index: its stored text is readable, but FTS
    # cannot retrieve the corrupted ART═CULO heading by article tokens.
    monkeypatch.setattr(
        server, "_legal_citation_fts_query", lambda _intent: '"missinglegal"'
    )
    monkeypatch.setattr(
        server, "_legal_article_fts_query", lambda _intent: '"missingarticle"'
    )

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
    assert result["results"][0]["direct_legislation_match"] is True
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

    ordinary = server._content_search_v2("multa", limit=2)
    assert ordinary["search_strategy"] == "fts5_match_centered_hybrid"
    assert "legal_citation" not in ordinary
    assert "legislation_priority" not in ordinary["results"][0]
