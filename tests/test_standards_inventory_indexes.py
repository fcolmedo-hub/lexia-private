from __future__ import annotations

import sqlite3
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INSTALLER = ROOT / "scripts" / "install_standards_inventory_indexes.py"


def _database(path: Path) -> None:
    with sqlite3.connect(path) as con:
        con.executescript("""
            CREATE TABLE standards (
                standard_uid TEXT PRIMARY KEY, publication_status TEXT, review_status TEXT
            );
            CREATE TABLE canonical_standards (
                canonical_uid TEXT PRIMARY KEY, status TEXT
            );
            CREATE TABLE standard_occurrences (
                standard_uid TEXT PRIMARY KEY, canonical_uid TEXT
            );
            CREATE TABLE quotes (
                standard_uid TEXT, page_start INTEGER, quote_text TEXT
            );
            CREATE INDEX idx_standards_publication ON standards(publication_status);
            CREATE INDEX idx_standards_review ON standards(review_status);
        """)
        con.executemany(
            "INSERT INTO standards VALUES(?,?,?)",
            [(f"STD-{i}", "published" if i % 5 else "blocked", "validated")
             for i in range(7202)],
        )
        con.executemany(
            "INSERT INTO canonical_standards VALUES(?,?)",
            [(f"CAN-{i}", "confirmed") for i in range(7202)],
        )
        con.executemany(
            "INSERT INTO standard_occurrences VALUES(?,?)",
            [(f"STD-{i}", f"CAN-{i}") for i in range(7202)],
        )
        con.executemany(
            "INSERT INTO quotes VALUES(?,?,?)",
            [(f"STD-{i}", 1, "cita literal") for i in range(7202)],
        )


def _run(path: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(INSTALLER), "--db", str(path), *args],
        cwd=ROOT, capture_output=True, text=True,
    )


def test_check_is_read_only_and_install_preserves_rows(tmp_path: Path) -> None:
    db = tmp_path / "standards.sqlite3"
    _database(db)
    before = db.read_bytes()
    check = _run(db, "--check")
    assert check.returncode == 0, check.stderr
    assert db.read_bytes() == before

    install = _run(db)
    assert install.returncode == 0, install.stderr
    assert "estándares: 7202" in install.stdout
    backups = list(tmp_path.glob("standards-antes-indices-*.sqlite3"))
    assert len(backups) == 1
    with sqlite3.connect(db) as con, sqlite3.connect(backups[0]) as previous:
        assert con.execute("SELECT COUNT(*) FROM standards").fetchone()[0] == 7202
        assert previous.execute("SELECT COUNT(*) FROM standards").fetchone()[0] == 7202
        plan = con.execute("EXPLAIN QUERY PLAN SELECT COUNT(*) FROM canonical_standards WHERE status='confirmed'").fetchall()
        assert any("idx_canonical_status_uid" in row[3] for row in plan)
        evidence_plan = con.execute("""EXPLAIN QUERY PLAN SELECT COUNT(*) FROM standards s
            WHERE s.publication_status='published' AND NOT EXISTS (
            SELECT 1 FROM quotes q WHERE q.standard_uid=s.standard_uid
            AND TRIM(q.quote_text)<>'' AND q.page_start>0)""").fetchall()
        assert any("idx_quotes_valid_standard" in row[3] for row in evidence_plan)

    again = _run(db)
    assert again.returncode == 0, again.stderr
    assert len(list(tmp_path.glob("standards-antes-indices-*.sqlite3"))) == 1


def test_conflicting_index_is_rejected_without_changes(tmp_path: Path) -> None:
    db = tmp_path / "standards.sqlite3"
    _database(db)
    with sqlite3.connect(db) as con:
        con.execute("CREATE INDEX idx_canonical_status_uid ON canonical_standards(canonical_uid)")
    before = db.read_bytes()
    result = _run(db, "--check")
    assert result.returncode != 0
    assert "columnas diferentes" in result.stderr
    assert db.read_bytes() == before
