import sqlite3

from knowledge.citation_analyzer import CitationAnalyzer


def prepare(path):
    con = sqlite3.connect(path)
    con.executescript(
        """
        CREATE TABLE citation_edges (
            source_document_path TEXT NOT NULL,
            citation_key TEXT NOT NULL,
            target_document_path TEXT,
            citation_text TEXT NOT NULL,
            resolved INTEGER NOT NULL DEFAULT 0,
            confidence REAL NOT NULL DEFAULT 0,
            PRIMARY KEY(source_document_path, citation_key)
        );
        """
    )
    rows = [
        ("a", "1", None, "Fallos 326:3899", 0, 0),
        ("a", "2", None, "Filcrosa SA c/ Municipalidad", 0, 0),
        ("b", "3", None, "Expte. 1234/2020", 0, 0),
        ("b", "4", None, "Corte Suprema", 0, 0),
        ("b", "5", None, "12/03/2020", 0, 0),
        ("c", "6", None, "Ley 11683 art. 18", 0, 0),
        ("c", "7", None, "doctrina aplicable", 0, 0),
        ("c", "8", None, "-", 0, 0),
    ]
    con.executemany(
        """
        INSERT INTO citation_edges (
            source_document_path,
            citation_key,
            target_document_path,
            citation_text,
            resolved,
            confidence
        )
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        rows,
    )
    con.commit()
    con.close()


def test_classification(tmp_path):
    db = tmp_path / "knowledge.sqlite3"
    prepare(db)

    analyzer = CitationAnalyzer(db)
    result = analyzer.analyze()
    summary = result["summary"]

    assert summary.total_edges == 8
    assert summary.fallos_refs == 1
    assert summary.case_names == 1
    assert summary.case_numbers == 1
    assert summary.tribunal_only == 1
    assert summary.date_only == 1
    assert summary.normative_refs == 1
    assert summary.generic_text == 1
    assert summary.invalid_like == 1
