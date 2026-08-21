import sqlite3

from knowledge.jurisprudential_citation_resolver import (
    JurisprudentialCitationResolver,
)


def prepare(path):
    con = sqlite3.connect(path)
    con.execute(
        """
        CREATE TABLE knowledge_documents (
            document_path TEXT PRIMARY KEY,
            document_name TEXT NOT NULL,
            court TEXT NOT NULL DEFAULT '',
            jurisdiction TEXT NOT NULL DEFAULT '',
            decision_date TEXT NOT NULL DEFAULT ''
        )
        """
    )
    con.executemany(
        """
        INSERT INTO knowledge_documents
        (document_path, document_name, court, jurisdiction, decision_date)
        VALUES (?, ?, ?, ?, ?)
        """,
        [
            (
                "filcrosa.pdf",
                "Filcrosa SA c Municipalidad de Avellaneda.pdf",
                "Corte Suprema de Justicia de la Nación",
                "Nacional/Federal",
                "2003-09-30",
            ),
            (
                "candy.pdf",
                "Candy SA c AFIP.pdf",
                "Corte Suprema de Justicia de la Nación",
                "Nacional/Federal",
                "2009-07-03",
            ),
            (
                "otro.pdf",
                "Empresa Común SA c AFIP.pdf",
                "Cámara Federal",
                "Nacional/Federal",
                "2009-01-01",
            ),
        ],
    )
    con.commit()
    con.close()


def test_resolves_filcrosa_without_full_scan(tmp_path):
    db = tmp_path / "knowledge.sqlite3"
    prepare(db)
    resolver = JurisprudentialCitationResolver(db)

    result = resolver.resolve(
        "conf. Filcrosa S.A. c/ Municipalidad de Avellaneda"
    )

    assert result.target_document_path == "filcrosa.pdf"
    assert result.confidence >= 0.86


def test_generic_query_does_not_force_resolution(tmp_path):
    db = tmp_path / "knowledge.sqlite3"
    prepare(db)
    resolver = JurisprudentialCitationResolver(db)

    result = resolver.resolve("AFIP sentencia 2009")

    assert result.target_document_path is None
