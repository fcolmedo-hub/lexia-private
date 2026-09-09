from __future__ import annotations

import sqlite3
from pathlib import Path

from app.ui2 import standards_api
from services.standards_canonicalizer import rebuild_canonical_groups


ROOT = Path(__file__).resolve().parents[1]


def _make_db(path: Path) -> None:
    con = sqlite3.connect(path)
    con.executescript((ROOT / "standards" / "schema.sql").read_text(encoding="utf-8"))
    con.execute(
        """INSERT INTO documents(source_key,document_name,document_path,court,judgment_date)
           VALUES('doc:1','Uno.pdf','/tmp/uno.pdf','CSJN','2025-01-01')"""
    )
    con.execute(
        """INSERT INTO documents(source_key,document_name,document_path,court,judgment_date)
           VALUES('doc:2','Dos.pdf','/tmp/dos.pdf','CSJN','2024-01-01')"""
    )
    docs = [row[0] for row in con.execute("SELECT document_id FROM documents ORDER BY document_id")]
    con.execute(
        """INSERT INTO standards(
               standard_uid,document_id,statement,speaker,source_speaker,treatment,
               source_fingerprint,review_status,publication_status
           ) VALUES('STD-1',?,'Regla primera','mayoria','mayoria','adopta',
                    'fp-1','validated','ready')""",
        (docs[0],),
    )
    con.execute(
        """INSERT INTO standards(
               standard_uid,document_id,statement,speaker,source_speaker,treatment,
               source_fingerprint,review_status,publication_status
           ) VALUES('STD-2',?,'La misma regla expresada de otro modo','mayoria','mayoria','adopta',
                    'fp-2','validated','ready')""",
        (docs[1],),
    )
    con.execute(
        """INSERT INTO relations(
               relation_id,from_standard_uid,to_standard_uid,relation_type,status,rationale
           ) VALUES(1,'STD-1','STD-2','duplicate_of','proposed','posible equivalencia')"""
    )
    rebuild_canonical_groups(con)
    con.commit()
    con.close()


def test_confirming_suggestion_rebuilds_one_canonical_standard(tmp_path):
    db = tmp_path / "standards.sqlite3"
    _make_db(db)
    previous = standards_api.SERVICE.db_path
    standards_api.SERVICE.db_path = db
    try:
        result = standards_api._canonical_decision(
            {"relation_id": 1, "decision": "confirm"}
        )
    finally:
        standards_api.SERVICE.db_path = previous

    con = sqlite3.connect(db)
    try:
        assert result["status"] == "confirmed"
        assert con.execute("SELECT status FROM relations WHERE relation_id=1").fetchone()[0] == "confirmed"
        assert con.execute("SELECT COUNT(*) FROM canonical_standards").fetchone()[0] == 1
        assert con.execute("SELECT COUNT(*) FROM standard_occurrences").fetchone()[0] == 2
    finally:
        con.close()

def test_publication_decision_publishes_reserved_standard_and_audits_it(tmp_path):
    db = tmp_path / "standards.sqlite3"
    _make_db(db)
    con = sqlite3.connect(db)
    con.execute(
        """UPDATE standards SET review_status='needs_review',publication_status='blocked'
           WHERE standard_uid='STD-2'"""
    )
    con.commit()
    con.close()

    previous = standards_api.SERVICE.db_path
    standards_api.SERVICE.db_path = db
    try:
        result = standards_api._publication_decision(
            {"standard_uid": "STD-2", "decision": "publish"}
        )
    finally:
        standards_api.SERVICE.db_path = previous

    con = sqlite3.connect(db)
    try:
        assert result["review_status"] == "validated"
        assert result["publication_status"] == "ready"
        assert con.execute(
            "SELECT review_status,publication_status FROM standards WHERE standard_uid='STD-2'"
        ).fetchone() == ("validated", "ready")
        assert con.execute(
            "SELECT decision FROM standard_publication_decisions WHERE standard_uid='STD-2'"
        ).fetchone()[0] == "publish"
    finally:
        con.close()

def test_publication_decision_rejects_without_deleting_traceability(tmp_path):
    db = tmp_path / "standards.sqlite3"
    _make_db(db)
    con = sqlite3.connect(db)
    con.execute(
        """UPDATE standards SET review_status='needs_review',publication_status='blocked'
           WHERE standard_uid='STD-2'"""
    )
    con.commit()
    con.close()

    previous = standards_api.SERVICE.db_path
    standards_api.SERVICE.db_path = db
    try:
        result = standards_api._publication_decision(
            {"standard_uid": "STD-2", "decision": "reject"}
        )
    finally:
        standards_api.SERVICE.db_path = previous

    con = sqlite3.connect(db)
    try:
        assert result["review_status"] == "rejected"
        assert con.execute(
            "SELECT review_status,publication_status FROM standards WHERE standard_uid='STD-2'"
        ).fetchone() == ("rejected", "hidden")
        assert con.execute(
            "SELECT COUNT(*) FROM standards WHERE standard_uid='STD-2'"
        ).fetchone()[0] == 1
        assert con.execute(
            "SELECT decision FROM standard_publication_decisions WHERE standard_uid='STD-2'"
        ).fetchone()[0] == "reject"
    finally:
        con.close()

    inventory = standards_api.StandardsService(db).inventory()
    assert inventory["occurrences_total"] == 2
    assert inventory["rejected_occurrences"] == 1
