from pathlib import Path
import sqlite3

from knowledge.citation_graph import CitationGraphEngine


def prepare_database(path):
    con = sqlite3.connect(path)
    con.executescript(
        """
        CREATE TABLE knowledge_documents (
            document_path TEXT PRIMARY KEY,
            content_hash TEXT NOT NULL DEFAULT '',
            document_name TEXT NOT NULL,
            category TEXT NOT NULL DEFAULT '',
            court TEXT NOT NULL DEFAULT '',
            jurisdiction TEXT NOT NULL DEFAULT '',
            decision_date TEXT NOT NULL DEFAULT '',
            document_type TEXT NOT NULL DEFAULT '',
            matter TEXT NOT NULL DEFAULT '',
            analyzed_at TEXT
        );

        CREATE TABLE document_citations (
            document_path TEXT NOT NULL,
            citation TEXT NOT NULL,
            normalized_citation TEXT NOT NULL
        );
        """
    )
    con.executemany(
        """
        INSERT INTO knowledge_documents (
            document_path,
            content_hash,
            document_name,
            category,
            court,
            jurisdiction,
            decision_date,
            document_type,
            matter
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            (
                "A.pdf",
                "hash-a",
                "Candy c EN AFIP.pdf",
                "Jurisprudencia",
                "Corte Suprema de Justicia de la Nación",
                "Nacional/Federal",
                "2009-07-03",
                "Sentencia",
                "Derecho tributario",
            ),
            (
                "B.pdf",
                "hash-b",
                "Filcrosa SA c Municipalidad.pdf",
                "Jurisprudencia",
                "Corte Suprema de Justicia de la Nación",
                "Nacional/Federal",
                "2003-09-30",
                "Sentencia",
                "Derecho tributario",
            ),
            (
                "C.pdf",
                "hash-c",
                "Otro fallo.pdf",
                "Jurisprudencia",
                "Cámara Federal",
                "Nacional/Federal",
                "2010-01-01",
                "Sentencia",
                "Derecho tributario",
            ),
        ],
    )
    con.executemany(
        """
        INSERT INTO document_citations (
            document_path,
            citation,
            normalized_citation
        )
        VALUES (?, ?, ?)
        """,
        [
            (
                "A.pdf",
                "Filcrosa SA c Municipalidad",
                "filcrosasacmunicipalidad",
            ),
            (
                "A.pdf",
                "Fallos 326:3899",
                "fallos3263899",
            ),
            ("A.pdf", "-", ""),
            ("C.pdf", "*", ""),
        ],
    )
    con.commit()
    con.close()


def test_graph_builds_and_filters_invalid(tmp_path):
    db = tmp_path / "knowledge.sqlite3"
    prepare_database(db)

    engine = CitationGraphEngine(db)
    stats = engine.rebuild()

    assert stats.edges == 2
    assert stats.resolved_edges >= 1
    assert stats.unresolved_edges >= 0


def test_outgoing_and_incoming(tmp_path):
    db = tmp_path / "knowledge.sqlite3"
    prepare_database(db)

    engine = CitationGraphEngine(db)
    engine.rebuild()

    outgoing = engine.outgoing("A.pdf")
    incoming = engine.incoming("B.pdf")

    assert len(outgoing) == 2
    assert len(incoming) >= 1
    assert incoming[0]["source_document_path"] == "A.pdf"


def test_repository_is_patched():
    source = Path(
        "knowledge/repository.py"
    ).read_text(encoding="utf-8")

    assert "CitationGraphEngine" in source
    assert "self.citation_graph.rebuild()" in source


def test_knowledge_engine_exposes_graph():
    source = Path(
        "services/knowledge_engine.py"
    ).read_text(encoding="utf-8")

    assert "citation_graph_stats" in source
    assert "citation_graph_outgoing" in source
    assert "citation_graph_incoming" in source
