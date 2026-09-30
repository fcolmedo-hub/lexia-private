"""Visible canonical counts must scan occurrences once, including on large batches."""

import sqlite3
from pathlib import Path

from services.standards_service import StandardsService


SCHEMA = Path(__file__).resolve().parents[1] / "standards" / "schema.sql"


def test_visible_canonical_inventory_and_search(tmp_path: Path) -> None:
    db = tmp_path / "standards.sqlite3"
    with sqlite3.connect(db) as con:
        con.executescript(SCHEMA.read_text(encoding="utf-8"))
        con.executemany(
            "INSERT INTO documents(document_id,source_key,document_name,court) VALUES(?,?,?,?)",
            [(1, "one", "Fallo uno", "CSJN"),
             (2, "two", "Fallo dos", "CNCAF")],
        )
        con.executemany(
            """INSERT INTO standards(standard_uid,document_id,statement,speaker,
                source_speaker,treatment,source_fingerprint,review_status,publication_status)
                VALUES(?,?,?,?,?,?,?,?,?)""",
            [("A", 1, "Regla A", "mayoria", "mayoria", "adopta", "A", "validated", "published"),
             ("B", 2, "Regla B", "mayoria", "mayoria", "adopta", "B", "validated", "ready"),
             ("C", 1, "Regla C", "mayoria", "mayoria", "adopta", "C", "rejected", "hidden"),
             ("D", 2, "Regla D", "mayoria", "mayoria", "adopta", "D", "rejected", "hidden"),
             ("E", 1, "Regla E", "mayoria", "mayoria", "adopta", "E", "validated", "ready")],
        )
        con.executemany(
            "INSERT INTO canonical_standards(canonical_uid,statement,representative_standard_uid,status) VALUES(?,?,?,?)",
            [("CAN-1", "Regla A", "A", "confirmed"),
             ("CAN-2", "Regla D", "D", "confirmed"),
             ("CAN-3", "Regla E", "E", "proposed")],
        )
        con.executemany(
            "INSERT INTO standard_occurrences(standard_uid,canonical_uid,match_basis) VALUES(?,?,?)",
            [("A", "CAN-1", "singleton"), ("B", "CAN-1", "confirmed_duplicate"),
             ("C", "CAN-1", "confirmed_duplicate"), ("D", "CAN-2", "singleton"),
             ("E", "CAN-3", "singleton")],
        )

    service = StandardsService(db)
    inventory = service.inventory()
    assert inventory["occurrences_total"] == 5
    assert inventory["visible_occurrences"] == 3
    assert inventory["canonical_standards_total"] == 2
    assert inventory["visible_canonical_standards"] == 1
    assert service.count() == 1
    assert service.search()["total"] == 1
    assert service.search(court="CNCAF")["total"] == 1
    assert service.search(court="CSJN")["total"] == 1

    with sqlite3.connect(db) as con:
        sql = ("SELECT COUNT(*) FROM canonical_standards c WHERE c.status='confirmed' "
               "AND " + service._visible_canonical_sql())
        plan = [row[3] for row in con.execute("EXPLAIN QUERY PLAN " + sql)]
    assert any("LIST SUBQUERY" in step for step in plan)
    assert not any("CORRELATED" in step for step in plan)
