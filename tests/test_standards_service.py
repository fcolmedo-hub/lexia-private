from pathlib import Path
import sqlite3

from services.standards_service import StandardsService
from services.standards_canonicalizer import rebuild_canonical_groups


SCHEMA = """
CREATE TABLE documents(document_id INTEGER PRIMARY KEY, source_key TEXT UNIQUE, document_name TEXT, document_path TEXT, court TEXT, judgment_date TEXT, metadata_json TEXT DEFAULT '{}');
CREATE TABLE standards(standard_uid TEXT PRIMARY KEY, document_id INTEGER, local_identifier TEXT, statement TEXT, speaker TEXT, source_speaker TEXT, treatment TEXT, conditions_json TEXT DEFAULT '[]', consequence TEXT, exceptions_json TEXT DEFAULT '[]', review_status TEXT, publication_status TEXT, canonical_uid TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP);
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
    con.execute("INSERT INTO documents VALUES(3,'doc:3','Fallo C','/tmp/c.pdf','CNCAF','2023-01-02','{}')")
    standards = [
        ('STD-A',1,'A','La reserva legal tributaria impide delegar aspectos sustanciales.','mayoria','mayoria','adopta','[]',None,'[]','validated','ready',None),
        ('STD-B',2,'B','Los derechos de exportación tienen naturaleza tributaria.','mayoria','mayoria','adopta','[]',None,'[]','validated','published',None),
        ('STD-C',2,'C','Estándar bloqueado.','mayoria','mayoria','adopta','[]',None,'[]','needs_review','blocked',None),
        ('STD-D',3,'D','No pueden delegarse los elementos sustanciales del tributo por el principio de reserva legal.','mayoria','mayoria','adopta','[]',None,'[]','validated','ready',None),
    ]
    con.executemany("""INSERT INTO standards(
        standard_uid,document_id,local_identifier,statement,speaker,source_speaker,
        treatment,conditions_json,consequence,exceptions_json,review_status,
        publication_status,canonical_uid
    ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)""", standards)
    con.executemany("INSERT INTO standards_fts VALUES(?,?,?,?,?)", [(x[0],x[3],'','','') for x in standards])
    con.execute("INSERT INTO quotes VALUES(1,'STD-A',1,'c1',4,4,'[\"U1\"]','cita literal','exact')")
    con.execute("INSERT INTO tags VALUES(1,'tributario')")
    con.execute("INSERT INTO standard_tags VALUES('STD-A',1)")
    con.execute("INSERT INTO relations VALUES(1,'STD-B','STD-A','supports','proposed','fundamento')")
    con.execute("INSERT INTO relations VALUES(2,'STD-A','STD-B','contradicts','proposed','requiere revisión')")
    con.execute("INSERT INTO relations VALUES(3,'STD-D','STD-A','duplicate_of','confirmed','misma regla auditada')")
    con.execute("INSERT INTO relations VALUES(4,'STD-A','STD-B','duplicate_of','proposed','posible equivalencia')")
    rebuild_canonical_groups(con)
    con.commit()
    con.close()
    return path


def test_search_filters_and_visibility(tmp_path):
    service = StandardsService(make_db(tmp_path))
    result = service.search(text='tributaria', tags=['tributario'], court='CSJN', speaker='mayoria', treatment='adopta')
    assert result['total'] == 1
    assert result['items'][0]['representative_standard_uid'] == 'STD-A'


def test_blank_search_returns_every_visible_standard(tmp_path):
    service = StandardsService(make_db(tmp_path))

    result = service.search()

    assert result['total'] == 2
    assert result['total'] == 2
    assert {item['representative_standard_uid'] for item in result['items']} == {'STD-A', 'STD-B'}


def test_search_accepts_free_form_legal_punctuation(tmp_path):
    service = StandardsService(make_db(tmp_path))

    result = service.search(text='¿reserva legal, art. 17?')

    assert result['total'] == 1
    assert result['items'][0]['representative_standard_uid'] == 'STD-A'


def test_search_uses_recall_oriented_terms(tmp_path):
    service = StandardsService(make_db(tmp_path))

    result = service.search(text='reserva exportación')

    assert result['total'] == 2
    assert {item['representative_standard_uid'] for item in result['items']} == {'STD-A', 'STD-B'}


def test_count_matches_searchable_standards(tmp_path):
    service = StandardsService(make_db(tmp_path))

    assert service.count() == 2


def test_inventory_distinguishes_stored_and_published_standards(tmp_path):
    service = StandardsService(make_db(tmp_path))

    assert service.inventory() == {
        'canonical_standards_total': 3,
        'visible_canonical_standards': 2,
        'occurrences_total': 4,
        'visible_occurrences': 3,
        'reserved_occurrences': 1,
    }


def test_reserved_queue_includes_evidence_and_reason(tmp_path):
    service = StandardsService(make_db(tmp_path))

    result = service.reserved_standards()
    detail = service.get_reserved_standard('STD-C')

    assert result['total'] == 1
    assert result['items'][0]['standard_uid'] == 'STD-C'
    assert result['items'][0]['reserve_reason'] == 'Requiere validación jurídica'
    assert detail is not None
    assert detail['document_name'] == 'Fallo B'
    assert detail['quotes'] == []
    assert service.get_reserved_standard('STD-A') is None


def test_detail_quotes_and_publication_policy(tmp_path):
    service = StandardsService(make_db(tmp_path))
    detail = service.get_standard('STD-A')
    assert detail is not None
    assert detail['canonical_uid'].startswith('CAN-')
    assert detail['occurrence_count'] == 2
    assert detail['document_count'] == 2
    assert {item['standard_uid'] for item in detail['occurrences']} == {'STD-A', 'STD-D'}
    assert detail['quotes'][0]['quote_text'] == 'cita literal'
    assert detail['tags'] == ['tributario']
    assert [r['relation_type'] for r in detail['relations']] == ['supports']
    assert detail['canonical_suggestions'][0]['other']['statement'].startswith('Los derechos')
    assert service.get_standard('STD-C') is None


def test_graph_and_investigation_source(tmp_path):
    service = StandardsService(make_db(tmp_path))
    graph = service.graph('STD-A')
    assert graph['ok'] is True
    assert len(graph['nodes']) == 2
    sources = service.investigation_sources('reserva', limit=5)
    assert sources[0]['source_type'] == 'legal_standard'
    assert sources[0]['quote'] == 'cita literal'
    assert sources[0]['document_count'] == 2
    assert len(sources[0]['supporting_sources']) == 2
