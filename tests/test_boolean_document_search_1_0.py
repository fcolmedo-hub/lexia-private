import sqlite3

from search.boolean_query import (
    parse_boolean_query,
)
from search.boolean_document_search import (
    search_boolean_documents,
)


def make_database(path):
    con = sqlite3.connect(path)

    con.execute("""
        CREATE TABLE documents (
            path TEXT PRIMARY KEY,
            name TEXT,
            category TEXT,
            is_deleted INTEGER DEFAULT 0
        )
    """)

    con.execute("""
        CREATE TABLE fragments (
            document_path TEXT,
            fragment_index INTEGER,
            page_start INTEGER,
            page_end INTEGER
        )
    """)

    con.execute("""
        CREATE VIRTUAL TABLE
        fragments_fts USING fts5(
            document_path UNINDEXED,
            fragment_index UNINDEXED,
            category UNINDEXED,
            document_name UNINDEXED,
            text_content
        )
    """)

    return con


def add_fragment(
    con,
    path,
    name,
    fragment,
    page,
    text,
):
    con.execute(
        """
        INSERT OR IGNORE INTO
        documents(
            path,
            name,
            category,
            is_deleted
        )
        VALUES (
            ?,?,
            'Jurisprudencia',
            0
        )
        """,
        (path, name),
    )

    con.execute(
        """
        INSERT INTO fragments
        VALUES (?,?,?,?)
        """,
        (
            path,
            fragment,
            page,
            page,
        ),
    )

    con.execute(
        """
        INSERT INTO fragments_fts
        VALUES (?,?,?,?,?)
        """,
        (
            path,
            fragment,
            "Jurisprudencia",
            name,
            text,
        ),
    )


def test_and_across_400_pages(
    tmp_path,
):
    db = tmp_path / "db.sqlite3"
    con = make_database(db)

    add_fragment(
        con,
        "/fallo.pdf",
        "fallo.pdf",
        1,
        12,
        "cuestión de aduana",
    )

    add_fragment(
        con,
        "/fallo.pdf",
        "fallo.pdf",
        250,
        401,
        "importación temporal",
    )

    con.commit()
    con.close()

    q = parse_boolean_query(
        "aduana AND importación"
    )

    rows = search_boolean_documents(
        db,
        q,
    )

    assert len(rows) == 1


def test_not_excludes_whole_document(
    tmp_path,
):
    db = tmp_path / "db.sqlite3"
    con = make_database(db)

    add_fragment(
        con,
        "/a.pdf",
        "a.pdf",
        1,
        10,
        "aduana",
    )

    add_fragment(
        con,
        "/a.pdf",
        "a.pdf",
        300,
        410,
        "contrabando",
    )

    add_fragment(
        con,
        "/b.pdf",
        "b.pdf",
        1,
        20,
        "aduana",
    )

    con.commit()
    con.close()

    q = parse_boolean_query(
        "aduana NOT contrabando"
    )

    rows = search_boolean_documents(
        db,
        q,
    )

    paths = {
        row["document_path"]
        for row in rows
    }

    assert "/a.pdf" not in paths
    assert "/b.pdf" in paths


def test_near_inside_fragment(
    tmp_path,
):
    db = tmp_path / "db.sqlite3"
    con = make_database(db)

    add_fragment(
        con,
        "/a.pdf",
        "a.pdf",
        1,
        50,
        "plazo razonable debido proceso",
    )

    con.commit()
    con.close()

    q = parse_boolean_query(
        '"plazo razonable" '
        'NEAR/5 '
        '"debido proceso"'
    )

    rows = search_boolean_documents(
        db,
        q,
    )

    assert len(rows) == 1


def test_near_crosses_fragment_boundary(
    tmp_path,
):
    db = tmp_path / "db.sqlite3"
    con = make_database(db)

    add_fragment(
        con,
        "/a.pdf",
        "a.pdf",
        10,
        100,
        "fundamentos sobre el plazo razonable",
    )

    add_fragment(
        con,
        "/a.pdf",
        "a.pdf",
        11,
        101,
        "y el debido proceso constitucional",
    )

    con.commit()
    con.close()

    q = parse_boolean_query(
        '"plazo razonable" '
        'NEAR/5 '
        '"debido proceso"'
    )

    rows = search_boolean_documents(
        db,
        q,
    )

    assert len(rows) == 1
    assert rows[0]["near_match"] is True
    assert rows[0]["page_start"] == 100
    assert rows[0]["page_end"] == 101


def test_near_rejects_far_terms(
    tmp_path,
):
    db = tmp_path / "db.sqlite3"
    con = make_database(db)

    add_fragment(
        con,
        "/a.pdf",
        "a.pdf",
        1,
        100,
        "responsabilidad",
    )

    add_fragment(
        con,
        "/a.pdf",
        "a.pdf",
        2,
        101,
        (
            "palabra " * 30
            + "solidaria"
        ),
    )

    con.commit()
    con.close()

    q = parse_boolean_query(
        "responsabilidad "
        "NEAR/5 "
        "solidaria"
    )

    rows = search_boolean_documents(
        db,
        q,
    )

    assert rows == []


def test_near_plus_document_and(
    tmp_path,
):
    db = tmp_path / "db.sqlite3"
    con = make_database(db)

    add_fragment(
        con,
        "/a.pdf",
        "a.pdf",
        1,
        20,
        "plazo razonable",
    )

    add_fragment(
        con,
        "/a.pdf",
        "a.pdf",
        2,
        21,
        "debido proceso",
    )

    add_fragment(
        con,
        "/a.pdf",
        "a.pdf",
        300,
        405,
        "constitucionalidad",
    )

    con.commit()
    con.close()

    q = parse_boolean_query(
        '("plazo razonable" '
        'NEAR/5 '
        '"debido proceso") '
        'AND constitucionalidad'
    )

    rows = search_boolean_documents(
        db,
        q,
    )

    assert len(rows) == 1
