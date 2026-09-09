from __future__ import annotations

import sqlite3

from services.standards_canonicalizer import (
    normalize_exact_statement,
    rebuild_canonical_groups,
)


def _database() -> sqlite3.Connection:
    con = sqlite3.connect(":memory:")
    con.executescript(
        """
        PRAGMA foreign_keys=ON;
        CREATE TABLE standards(
            standard_uid TEXT PRIMARY KEY,
            document_id INTEGER,
            local_identifier TEXT,
            statement TEXT,
            speaker TEXT,
            treatment TEXT,
            conditions_json TEXT DEFAULT '[]',
            consequence TEXT,
            exceptions_json TEXT DEFAULT '[]',
            review_status TEXT,
            publication_status TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE relations(
            relation_id INTEGER PRIMARY KEY,
            from_standard_uid TEXT,
            to_standard_uid TEXT,
            relation_type TEXT,
            status TEXT,
            rationale TEXT
        );
        CREATE TABLE relation_decisions(
            candidate_id TEXT PRIMARY KEY,
            relation_id INTEGER,
            relation_type TEXT,
            decision_status TEXT,
            confidence TEXT
        );
        """
    )
    rows = [
        ("STD-1", 1, "La prescripción se suspende.", "mayoria", "adopta"),
        ("STD-2", 2, "La prescripcion se suspende!", "mayoria", "adopta"),
        ("STD-3", 3, "Mientras exista la cuestión previa no corre la prescripción.", "mayoria", "adopta"),
        ("STD-4", 4, "Otra regla independiente.", "mayoria", "adopta"),
    ]
    con.executemany(
        """INSERT INTO standards(
               standard_uid,document_id,statement,speaker,treatment,
               review_status,publication_status
           ) VALUES(?,?,?,?,?,'validated','ready')""",
        rows,
    )
    return con


def test_exact_normalization_is_typographic_only():
    assert normalize_exact_statement("Prescripción:  suspendida") == normalize_exact_statement(
        "PRESCRIPCION — suspendida."
    )
    assert normalize_exact_statement("regla tributaria") != normalize_exact_statement(
        "obligación fiscal"
    )


def test_rebuild_groups_exact_and_reviewed_duplicates_but_not_proposals():
    con = _database()
    con.execute(
        "INSERT INTO relations VALUES(1,'STD-3','STD-1','duplicate_of','proposed','auditada')"
    )
    con.execute(
        "INSERT INTO relation_decisions VALUES('CAN-1',1,'duplicate_of','reviewed','high')"
    )
    con.execute(
        "INSERT INTO relations VALUES(2,'STD-4','STD-1','duplicate_of','proposed','automática')"
    )

    stats = rebuild_canonical_groups(con)

    assert stats["standards"] == 4
    assert stats["canonical_standards"] == 2
    assert stats["multi_document_groups"] == 1
    assert stats["accepted_duplicate_edges"] == 1
    assert stats["proposed_duplicate_suggestions"] == 1
    group = con.execute(
        "SELECT canonical_uid FROM standard_occurrences WHERE standard_uid='STD-1'"
    ).fetchone()[0]
    members = {
        row[0]
        for row in con.execute(
            "SELECT standard_uid FROM standard_occurrences WHERE canonical_uid=?", (group,)
        )
    }
    assert members == {"STD-1", "STD-2", "STD-3"}
    assert con.execute(
        "SELECT canonical_uid FROM standard_occurrences WHERE standard_uid='STD-4'"
    ).fetchone()[0] != group


def test_rebuild_is_idempotent_and_indexes_alternative_wording():
    con = _database()
    con.execute(
        "INSERT INTO relations VALUES(1,'STD-3','STD-1','duplicate_of','confirmed','confirmada')"
    )
    first = rebuild_canonical_groups(con)
    mapping_before = list(
        con.execute(
            "SELECT standard_uid,canonical_uid FROM standard_occurrences ORDER BY standard_uid"
        )
    )

    second = rebuild_canonical_groups(con)
    mapping_after = list(
        con.execute(
            "SELECT standard_uid,canonical_uid FROM standard_occurrences ORDER BY standard_uid"
        )
    )

    assert first == second
    assert mapping_before == mapping_after
    match = con.execute(
        """SELECT canonical_uid FROM canonical_standards_fts
           WHERE canonical_standards_fts MATCH 'cuestion'"""
    ).fetchone()
    assert match is not None
