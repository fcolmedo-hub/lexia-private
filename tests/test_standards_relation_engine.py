import sqlite3
from pathlib import Path

from services.standards_relation_engine import apply_relation_decisions
from tools.preparar_canonicalizacion_estandares import build_candidates


def make_db(tmp_path: Path) -> Path:
    path = tmp_path / "standards.sqlite3"
    con = sqlite3.connect(path)
    con.executescript(
        """
        PRAGMA foreign_keys=ON;
        CREATE TABLE documents(document_id INTEGER PRIMARY KEY, document_name TEXT, court TEXT, judgment_date TEXT);
        CREATE TABLE standards(
            standard_uid TEXT PRIMARY KEY, document_id INTEGER, local_identifier TEXT, statement TEXT, speaker TEXT,
            source_speaker TEXT, treatment TEXT, conditions_json TEXT, consequence TEXT,
            exceptions_json TEXT, review_status TEXT, publication_status TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE quotes(standard_uid TEXT, evidence_index INTEGER, quote_text TEXT);
        CREATE TABLE relations(
            relation_id INTEGER PRIMARY KEY, from_standard_uid TEXT, to_standard_uid TEXT,
            relation_type TEXT, status TEXT, rationale TEXT,
            UNIQUE(from_standard_uid,to_standard_uid,relation_type)
        );
        INSERT INTO documents VALUES(1,'Fallo A','CSJN','2025-01-01');
        INSERT INTO standards(
            standard_uid,document_id,statement,speaker,source_speaker,treatment,
            conditions_json,consequence,exceptions_json,review_status,publication_status
        ) VALUES('STD-A',1,'La reserva legal impide delegar tributos','mayoria','mayoria','adopta','[]',NULL,'[]','validated','ready');
        INSERT INTO standards(
            standard_uid,document_id,statement,speaker,source_speaker,treatment,
            conditions_json,consequence,exceptions_json,review_status,publication_status
        ) VALUES('STD-B',1,'Los tributos requieren ley formal','mayoria','mayoria','adopta','[]',NULL,'[]','validated','ready');
        INSERT INTO quotes VALUES('STD-A',1,'cita A');
        INSERT INTO quotes VALUES('STD-B',1,'cita B');
        """
    )
    con.commit()
    con.close()
    return path


def classification(relation="supports", direction="a_to_b"):
    return {
        "candidate_id": "CAN-1",
        "a_uid": "STD-A",
        "b_uid": "STD-B",
        "valid": True,
        "relation": relation,
        "direction": direction,
        "confidence": "high",
        "rationale": "fundamento",
    }


def test_dry_run_does_not_change_database(tmp_path):
    db = make_db(tmp_path)
    result = apply_relation_decisions(db, [classification()])
    con = sqlite3.connect(db)
    assert result["positive_decisions"] == 1
    assert con.execute("SELECT COUNT(*) FROM relations").fetchone()[0] == 0
    assert con.execute("SELECT 1 FROM sqlite_master WHERE name='relation_decisions'").fetchone() is None


def test_apply_is_idempotent_and_records_none(tmp_path):
    db = make_db(tmp_path)
    first = apply_relation_decisions(db, [classification()], apply=True)
    second = apply_relation_decisions(db, [classification()], apply=True)
    none = apply_relation_decisions(
        db, [classification("none", "not_applicable")], apply=True
    )
    con = sqlite3.connect(db)
    assert first["sqlite_decisions_total"] == 1
    assert second["sqlite_decisions_total"] == 1
    assert second["sqlite_obsolete_proposed_removed"] == 0
    assert none["sqlite_obsolete_proposed_removed"] == 1
    assert con.execute("SELECT COUNT(*) FROM relations").fetchone()[0] == 0
    assert con.execute("SELECT relation_type FROM relation_decisions").fetchone()[0] == "none"


def test_confirmed_relation_is_preserved(tmp_path):
    db = make_db(tmp_path)
    apply_relation_decisions(db, [classification()], apply=True)
    con = sqlite3.connect(db)
    con.execute("UPDATE relations SET status='confirmed'")
    con.commit()
    con.close()

    result = apply_relation_decisions(
        db, [classification("none", "not_applicable")], apply=True
    )
    con = sqlite3.connect(db)
    assert result["sqlite_preserved_confirmed_or_rejected"] == 1
    assert con.execute("SELECT status FROM relations").fetchone()[0] == "confirmed"
    assert con.execute("SELECT relation_type FROM relation_decisions").fetchone()[0] == "supports"


def test_candidate_builder_skips_decided_pair(tmp_path):
    db = make_db(tmp_path)
    con = sqlite3.connect(db)
    all_candidates = build_candidates(con, 0.08, 1, 24)
    assert len(all_candidates) == 1
    skipped = build_candidates(
        con, 0.08, 1, 24, {all_candidates[0]["candidate_id"]}
    )
    assert skipped == []
