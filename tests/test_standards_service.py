from pathlib import Path
import sqlite3

from services.standards_service import StandardsService


SCHEMA = """
CREATE TABLE documents(document_id INTEGER PRIMARY KEY, source_key TEXT UNIQUE, document_name TEXT, document_path TEXT, court TEXT, judgment_date TEXT, metadata_json TEXT DEFAULT '{}');
CREATE TABLE standards(standard_uid TEXT PRIMARY KEY, document_id INTEGER, statement TEXT, speaker TEXT, source_speaker TEXT, treatment TEXT, conditions_json TEXT DEFAULT '[]', consequence TEXT, exceptions_json TEXT DEFAULT '[]', review_status TEXT, publication_status TEXT, canonical_uid TEXT);
CREATE TABLE quotes(quote_id INTEGER PRIMARY KEY, standard_uid TEXT, evidence_index INTEGER, chunk_id TEXT, page_start INTEGER, page_end INTEGER, unit_ids_json TEXT DEFAULT '[]', quote_text TEXT, validation TEXT);
CREATE TABLE relations(relation_id INTEGER PRIMARY KEY, from_standard_uid TEXT, to_standard_uid TEXT, relation_type TEXT, status TEXT, rationale TEXT);
CREATE TABLE tags(tag_id INTEGER PRIMARY KEY, name TEXT UNIQUE);
CREATE TABLE standard_tags(standard_uid TEXT, tag_id INTEGER);
CREATE VIRTUAL TABLE standards_fts USING fts5(standard_uid UNINDEXED, statement, conditions, consequence, exceptions, tokenize='unicode61 remove_diacritics 2');
"""


def make_db(tmp_path: Path) -> Path:
    path = tmp_path / "standards.sqlite3"
    con = sqlite3.connect(path)
    con.executescript(SCHEMA)
    con.execute("INSERT INTO documents VALUES(1,'doc:1','Fallo A','/tmp/a.pdf','CSJN','2025-01-02','{}')")
    con.execute("INSERT INTO documents VALUES(2,'doc:2','Fallo B','/tmp/b.pdf','CSJN','2024-01-02','{}')")
    standards = [
        ('STD-A',1,'La reserva legal tributaria impide delegar aspectos sustanciales.','mayoria','mayoria','adopta','[]',None,'[]','validated','ready',None),
        ('STD-B',2,'Los derechos de exportación tienen naturaleza tributaria.','mayoria','mayoria','adopta','[]',None,'[]','validated','published',None),
        ('STD-C',2,'Estándar bloqueado.','mayoria','mayoria','adopta','[]',None,'[]','needs_review','blocked',None),
    ]
    con.executemany("INSERT INTO standards VALUES(?,?,?,?,?,?,?,?,?,?,?,?)", standards)
    con.executemany("INSERT INTO standards_fts VALUES(?,?,?,?,?)", [(x[0],x[2],'','','') for x in standards])
    con.execute("INSERT INTO quotes VALUES(1,'STD-A',1,'c1',4,4,'[\"U1\"]','cita literal','exact')")
    con.execute("INSERT INTO tags VALUES(1,'tributario')")
    con.execute("INSERT INTO standard_tags VALUES('STD-A',1)")
    con.execute("INSERT INTO relations VALUES(1,'STD-B','STD-A','supports','proposed','fundamento')")
    con.execute("INSERT INTO relations VALUES(2,'STD-A','STD-B','contradicts','proposed','requiere revisión')")
    con.commit()
    con.close()
    return path


def test_search_filters_and_visibility(tmp_path):
    service = StandardsService(make_db(tmp_path))
    result = service.search(text='tributaria', tags=['tributario'], court='CSJN', speaker='mayoria', treatment='adopta')
    assert result['total'] == 1
    assert result['items'][0]['standard_uid'] == 'STD-A'


def test_detail_quotes_and_publication_policy(tmp_path):
    service = StandardsService(make_db(tmp_path))
    detail = service.get_standard('STD-A')
    assert detail is not None
    assert detail['quotes'][0]['quote_text'] == 'cita literal'
    assert detail['tags'] == ['tributario']
    assert [r['relation_type'] for r in detail['relations']] == ['supports']
    assert service.get_standard('STD-C') is None


def test_graph_and_investigation_source(tmp_path):
    service = StandardsService(make_db(tmp_path))
    graph = service.graph('STD-A')
    assert graph['ok'] is True
    assert {n['standard_uid'] for n in graph['nodes']} == {'STD-A','STD-B'}
    sources = service.investigation_sources('reserva', limit=5)
    assert sources[0]['source_type'] == 'legal_standard'
    assert sources[0]['quote'] == 'cita literal'
