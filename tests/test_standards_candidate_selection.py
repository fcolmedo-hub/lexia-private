import sqlite3
from pathlib import Path

from tools.preseleccionar_fallos_estandares import candidates


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
