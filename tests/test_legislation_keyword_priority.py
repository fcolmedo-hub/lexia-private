import ast
from pathlib import Path
import sqlite3
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]
UI2 = ROOT / "app/ui2"
sys.path.insert(0, str(UI2))
import legislation_intent
import legal_citations
from search.boolean_query import parse_boolean_query, BooleanQuerySyntaxError
from search.boolean_document_search import search_boolean_documents


@pytest.mark.parametrize("query", [
    "ley", "leyes", "código", "codigo civil", "códigos", "decreto", "decretos",
    "decreto-ley", "ordenanza", "ordenanzas", "resolución general", "resoluciones generales",
    "resolucion", "RG", "R.G.", "rg 1234", "constitución", "reglamento", "disposición",
    "acordada", "circular", "circulares", "tratado", "convenio", "estatuto", "normativa",
    "DNU", "D.N.U.", "orden ministerial", "órdenes ministeriales",
    "reglamentación", "legislacion", "instrucción general", "instrucciones generales",
    "decisión administrativa", "decisiones administrativas", "digesto", "texto ordenado",
])
def test_normative_keywords_do_not_require_article(query):
    assert legislation_intent.legislation_query_intent(query)


@pytest.mark.parametrize("query", ["leyenda", "codificación", "cargo", "urgencia", "prescripción tributaria"])
def test_word_boundaries_do_not_trigger_on_unrelated_words(query):
    assert not legislation_intent.legislation_query_intent(query)


def load_search(runtime):
    tree = ast.parse((UI2 / "server.py").read_text())
    prefixes = ("_content_", "_legal_", "_fts_")
    nodes = [node for node in tree.body if isinstance(node, ast.FunctionDef) and (node.name.startswith(prefixes) or node.name in {"_filter_category_key", "_filter_like_pattern", "_lexia321_norm"})
        or isinstance(node, ast.Assign) and any(isinstance(target, ast.Name) and target.id in {"_CONTENT_SEARCH_STOPWORDS", "_LEGAL_CODE_NAMES"} for target in node.targets)]
    namespace = {
        "__file__": str(UI2 / "server.py"), "Path": Path, "sqlite3": sqlite3,
        "RUNTIME_ROOT": runtime,
        "parse_boolean_query": parse_boolean_query,
        "BooleanQuerySyntaxError": BooleanQuerySyntaxError,
        "search_boolean_documents": search_boolean_documents,
        "_validated_filter_folder": lambda _category, folder: folder,
        "article_reference": legal_citations.article_reference,
        "legal_law_number": legal_citations.law_number,
        "article_matches": legal_citations.article_matches,
        "article_excerpt": legal_citations.article_excerpt,
        "instrument_in_text": legal_citations.instrument_in_text,
        "instrument_in_filename": legal_citations.instrument_in_filename,
    }
    exec(compile(ast.Module(body=nodes, type_ignores=[]), "real-search-handler", "exec"), namespace)
    return namespace["_content_search_v2"]


def catalog(runtime, statute, quoted, count=100):
    path = runtime / "lexia_catalog.sqlite3"
    with sqlite3.connect(path) as con:
        con.executescript("""CREATE TABLE documents(path TEXT PRIMARY KEY,name TEXT,category TEXT,is_deleted INTEGER DEFAULT 0);
            CREATE TABLE fragments(document_path TEXT,fragment_index INTEGER,text_content TEXT,page_start INTEGER,page_end INTEGER);
            CREATE VIRTUAL TABLE fragments_fts USING fts5(document_path UNINDEXED,fragment_index UNINDEXED,category UNINDEXED,document_name UNINDEXED,text_content);""")
        for i in range(count + 1):
            primary = i == count
            name = "Norma.pdf" if primary else f"Fallo {i:03}.pdf"
            category = "Legislación" if primary else "Jurisprudencia"
            text = statute if primary else quoted
            document_path = f"/Biblioteca/{category}/{name}"
            con.execute("INSERT INTO documents VALUES(?,?,?,0)", (document_path, name, category))
            con.execute("INSERT INTO fragments VALUES(?,0,?,1,1)", (document_path, text))
            con.execute("INSERT INTO fragments_fts VALUES(?,'0',?,?,?)", (document_path, category, name, text))
    return path


@pytest.mark.parametrize("query,statute", [
    ("ley 7055", "Ley 7055. Artículo 1. Régimen del recurso."),
    ("código civil", "Código Civil. Artículo 1. Disposiciones generales."),
    ("decreto 100", "Decreto 100. El Poder Ejecutivo dispone lo siguiente."),
    ("ordenanza 20", "Ordenanza 20. Régimen municipal."),
    ("resolución general 1234", "Resolución General 1234. Régimen tributario."),
    ("RG 1234", "Resolución General 1234. Régimen tributario."),
    ("R.G. 1234", "Resolución General 1234. Régimen tributario."),
])
def test_primary_legislation_enters_pool_before_many_quoting_judgments(tmp_path, query, statute):
    catalog(tmp_path, statute + " " + "texto " * 100, statute)
    result = load_search(tmp_path)(query, limit=1)
    assert result["results"][0]["category"] == "Legislación"
    assert result["results"][0]["legislation_priority"]
    assert result["legislation_intent"]["prioritized_category"] == "Legislación"
    assert result["query"] == query


def test_explicit_category_and_folder_filters_remain_authoritative(tmp_path):
    catalog(tmp_path, "Ley 7055 tributaria", "Ley 7055 tributaria")
    search = load_search(tmp_path)
    for query in ("ley 7055", "ley AND tributaria"):
        filtered = search(query, limit=1, category="Jurisprudencia")
        assert filtered["results"][0]["category"] == "Jurisprudencia"
        assert not filtered["results"][0]["legislation_priority"]
        assert filtered["legislation_intent"]["prioritized_category"] is None
        folder = search(query, limit=1, folder="/Biblioteca/Jurisprudencia")
        assert all("/Jurisprudencia/" in row["document_path"] for row in folder["results"])


@pytest.mark.parametrize("query", ["RG AND IVA NOT derogada", '"RG 1234" AND IVA NOT derogada'])
def test_boolean_priority_keeps_not_semantics_and_abbreviation_expansion(tmp_path, query):
    path = catalog(tmp_path, "Resolución General 1234 IVA vigente", "Resolución General 1234 IVA vigente")
    with sqlite3.connect(path) as con:
        con.execute("INSERT INTO documents VALUES('/Biblioteca/Legislación/Excluida.pdf','Excluida.pdf','Legislación',0)")
        con.execute("INSERT INTO fragments VALUES('/Biblioteca/Legislación/Excluida.pdf',0,'Resolución General 1234 IVA derogada',1,1)")
        con.execute("INSERT INTO fragments_fts VALUES('/Biblioteca/Legislación/Excluida.pdf','0','Legislación','Excluida.pdf','Resolución General 1234 IVA derogada')")
    result = load_search(tmp_path)(query, limit=1)
    assert result["results"][0]["document_name"] == "Norma.pdf"
    assert result["results"][0]["legislation_priority"]


def test_article_priority_and_focused_excerpt_are_preserved(tmp_path):
    catalog(tmp_path, "Artículo 5. Recurso admisible.\nArtículo 6. Otra materia.", "El art. 5 ley 7055 establece el recurso.", count=1)
    with sqlite3.connect(tmp_path / "lexia_catalog.sqlite3") as con:
        con.execute("UPDATE documents SET name='Ley 7055.pdf',path='/Biblioteca/Legislación/Ley 7055.pdf' WHERE category='Legislación'")
        con.execute("UPDATE fragments SET document_path='/Biblioteca/Legislación/Ley 7055.pdf' WHERE document_path='/Biblioteca/Legislación/Norma.pdf'")
        con.execute("UPDATE fragments_fts SET document_path='/Biblioteca/Legislación/Ley 7055.pdf',document_name='Ley 7055.pdf' WHERE category='Legislación'")
    result = load_search(tmp_path)("art. 5 ley 7055", limit=1)
    assert result["results"][0]["document_name"] == "Ley 7055.pdf"
    assert result["results"][0]["article_focused"]
    assert "Artículo 6" not in result["results"][0]["text"]


def test_ordinary_query_does_not_prioritize_legislation(tmp_path):
    catalog(tmp_path, "prescripción tributaria " + "texto " * 100, "prescripción tributaria", count=1)
    result = load_search(tmp_path)("prescripción tributaria", limit=1)
    assert result["results"][0]["category"] == "Jurisprudencia"
    assert "legislation_intent" not in result
    assert "legislation_priority" not in result["results"][0]
