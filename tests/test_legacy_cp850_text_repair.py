import sqlite3
from pathlib import Path

from core.text_encoding import (
    looks_like_legacy_cp850_mojibake,
    repair_legacy_cp850_mojibake,
)
from storage.catalog import DocumentCatalog


BROKEN = (
    "ART═CULO 5║.- La interposici¾n se acompa±arß en Santa Fe. "
    "Texto de la Ley N░7055. P┴GINA 2."
)
REPAIRED = (
    "ARTÍCULO 5º.- La interposición se acompañará en Santa Fe. "
    "Texto de la Ley N°7055. PÁGINA 2."
)


def test_repairs_known_cp850_font_mapping_without_touching_healthy_text() -> None:
    assert looks_like_legacy_cp850_mojibake(BROKEN) is True
    assert repair_legacy_cp850_mojibake(BROKEN) == REPAIRED

    healthy = "ARTÍCULO 5º.- El niño actuará también según la ley."
    assert looks_like_legacy_cp850_mojibake(healthy) is False
    assert repair_legacy_cp850_mojibake(healthy) == healthy

    german = "Die Straße ist groß; außerdem heißt es Fußgängerstraße."
    assert looks_like_legacy_cp850_mojibake(german) is False
    assert repair_legacy_cp850_mojibake(german) == german


def test_catalog_migration_repairs_document_fragments_and_fts(tmp_path: Path) -> None:
    database = tmp_path / "lexia_catalog.sqlite3"
    catalog = DocumentCatalog(database)
    path = "D:/Biblioteca/Legislacion/Santa Fe/Ley 7055.pdf"

    with catalog._connect() as connection:
        connection.execute(
            """
            INSERT INTO documents(
                path,name,category,extension,size,modified_ns,content_hash,
                vector_indexed_hash,text_content,metadata_json
            ) VALUES(?,?,?,?,?,?,?,?,?,?)
            """,
            (
                path, "Ley 7055.pdf", "Legislacion", ".pdf", 1, 1, "hash",
                "hash", BROKEN, '{"title":"Ley N░7055"}',
            ),
        )
        connection.execute(
            """
            INSERT INTO fragments(
                document_path,fragment_index,category,text_content,
                start_char,end_char,page_start,page_end
            ) VALUES(?,?,?,?,?,?,?,?)
            """,
            (path, 0, "Legislacion", BROKEN, 0, len(BROKEN), 1, 1),
        )
        connection.execute(
            "INSERT INTO fragments_fts VALUES(?,?,?,?,?)",
            (path, "0", "Legislacion", "Ley 7055.pdf", BROKEN),
        )
        # The first initialization marked the migration before this fixture
        # inserted legacy data; remove it to simulate an old real catalog.
        connection.execute(
            "DELETE FROM catalog_migrations WHERE name=?",
            ("repair_legacy_cp850_text_v1",),
        )

    DocumentCatalog(database)
    con = sqlite3.connect(database)
    try:
        document = con.execute(
            "SELECT text_content,metadata_json,vector_indexed_hash "
            "FROM documents WHERE path=?", (path,)
        ).fetchone()
        fragment = con.execute(
            "SELECT text_content FROM fragments WHERE document_path=?", (path,)
        ).fetchone()[0]
        fts = con.execute(
            "SELECT text_content FROM fragments_fts WHERE document_path=?", (path,)
        ).fetchone()[0]
        assert document == (REPAIRED, '{"title":"Ley N°7055"}', None)
        assert fragment == REPAIRED
        assert fts == REPAIRED
        assert con.execute(
            "SELECT COUNT(*) FROM fragments_fts "
            "WHERE fragments_fts MATCH 'articulo AND \"5º\"' "
            "AND document_path=?",
            (path,),
        ).fetchone()[0] == 1
    finally:
        con.close()
