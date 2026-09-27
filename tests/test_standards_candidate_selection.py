import sqlite3
from pathlib import Path

from tools.preseleccionar_fallos_estandares import candidates, within_folder


def test_selection_uses_indexed_judgments_in_folder_and_skips_imported(tmp_path: Path):
    catalog = tmp_path / "catalog.sqlite3"
    with sqlite3.connect(catalog) as connection:
        connection.executescript("""
            CREATE TABLE documents(path TEXT,category TEXT,is_deleted INTEGER);
            CREATE TABLE fragments(document_path TEXT,text_content TEXT);
            INSERT INTO documents VALUES('/Santa Fe/a.pdf','Jurisprudencia',0);
            INSERT INTO documents VALUES('/Santa Fe/b.pdf','Jurisprudencia',0);
            INSERT INTO documents VALUES('/Santa Fe/c.pdf','Jurisprudencia',0);
            INSERT INTO documents VALUES('/Santa Fe/d.pdf','Jurisprudencia',1);
            INSERT INTO documents VALUES('/Buenos Aires/e.pdf','Jurisprudencia',0);
            INSERT INTO documents VALUES('/Santa Fe/f.pdf','Doctrina',0);
            INSERT INTO fragments VALUES('/Santa Fe/a.pdf','cita');
            INSERT INTO fragments VALUES('/Santa Fe/b.pdf','cita');
            INSERT INTO fragments VALUES('/Santa Fe/c.pdf',' ');
            INSERT INTO fragments VALUES('/Santa Fe/d.pdf','cita');
            INSERT INTO fragments VALUES('/Buenos Aires/e.pdf','cita');
            INSERT INTO fragments VALUES('/Santa Fe/f.pdf','cita');
        """)
    db = tmp_path / "standards.sqlite3"
    with sqlite3.connect(db) as connection:
        connection.executescript("""
            CREATE TABLE documents(document_path TEXT);
            INSERT INTO documents VALUES('/Santa Fe/a.pdf');
        """)
    assert candidates(catalog, db, "Santa Fe", 250) == ["/Santa Fe/b.pdf"]
    assert candidates(catalog, tmp_path / "missing.sqlite3", "Santa Fe", 1) == ["/Santa Fe/a.pdf"]


def test_selection_excludes_same_pdf_imported_on_other_platform(tmp_path: Path):
    digest = "a" * 64
    catalog = tmp_path / "catalog.sqlite3"
    with sqlite3.connect(catalog) as connection:
        connection.executescript("""
            CREATE TABLE documents(path TEXT,category TEXT,is_deleted INTEGER,content_hash TEXT);
            CREATE TABLE fragments(document_path TEXT,text_content TEXT);
        """)
        connection.executemany("INSERT INTO documents VALUES(?, 'Jurisprudencia',0,?)", [
            ("D:/Jurisprudencia/duplicado.pdf", digest),
            ("D:/Jurisprudencia/nuevo.pdf", "b" * 64),
            ("D:/Jurisprudencia/copia.pdf", "b" * 64),
        ])
        connection.executemany("INSERT INTO fragments VALUES(?,'fallo')", [
            ("D:/Jurisprudencia/duplicado.pdf",),
            ("D:/Jurisprudencia/nuevo.pdf",),
            ("D:/Jurisprudencia/copia.pdf",),
        ])
    db = tmp_path / "standards.sqlite3"
    with sqlite3.connect(db) as connection:
        connection.executescript("""
            CREATE TABLE documents(document_path TEXT, source_key TEXT, metadata_json TEXT);
        """)
        connection.execute("INSERT INTO documents VALUES(?,?,?)", (
            "/Volumes/Jurisprudencia/duplicado.pdf", f"sha256:{digest}", "{}"
        ))
    assert candidates(catalog, db, "Jurisprudencia", 250) == ["D:/Jurisprudencia/copia.pdf"]


def test_exact_folder_includes_children_but_not_similarly_named_siblings(tmp_path: Path):
    catalog = tmp_path / "catalog.sqlite3"
    with sqlite3.connect(catalog) as connection:
        connection.executescript("""
            CREATE TABLE documents(path TEXT,category TEXT,is_deleted INTEGER);
            CREATE TABLE fragments(document_path TEXT,text_content TEXT);
            INSERT INTO documents VALUES('/library/Jurisprudencia/Santa Fe/a.pdf','Jurisprudencia',0);
            INSERT INTO documents VALUES('/library/Jurisprudencia/Santa Fe/Sala 1/b.pdf','Jurisprudencia',0);
            INSERT INTO documents VALUES('/library/Jurisprudencia/Santa Fe II/c.pdf','Jurisprudencia',0);
            INSERT INTO fragments VALUES('/library/Jurisprudencia/Santa Fe/a.pdf','fallo');
            INSERT INTO fragments VALUES('/library/Jurisprudencia/Santa Fe/Sala 1/b.pdf','fallo');
            INSERT INTO fragments VALUES('/library/Jurisprudencia/Santa Fe II/c.pdf','fallo');
        """)
    assert candidates(catalog, tmp_path / "missing.sqlite3", "Santa Fe", 250, folder="/library/Jurisprudencia/Santa Fe") == [
        "/library/Jurisprudencia/Santa Fe/a.pdf",
        "/library/Jurisprudencia/Santa Fe/Sala 1/b.pdf",
    ]
    assert within_folder(r"D:\LexIA\Jurisprudencia\Santa Fe\fallo.pdf", "d:/lexia/Jurisprudencia/Santa Fe")
    assert not within_folder(r"D:\LexIA\Jurisprudencia\Santa Fe II\fallo.pdf", "d:/lexia/Jurisprudencia/Santa Fe")
