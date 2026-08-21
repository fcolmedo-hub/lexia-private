from pathlib import Path

from storage.catalog import DocumentCatalog


def test_catalog_category_counts_and_browse_filtering(tmp_path: Path) -> None:
    catalog = DocumentCatalog(tmp_path / "catalog.sqlite3")
    with catalog._connect() as connection:
        connection.executemany(
            """
            INSERT INTO documents (
                path, name, category, extension, size, modified_ns,
                content_hash, text_content
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                ("D:/data/Doctrina/art1.pdf", "art1.pdf", "Doctrina", ".pdf", 100, 1, "h1", "texto"),
                ("D:/data/Doctrina/art2.pdf", "art2.pdf", "Doctrina", ".pdf", 200, 1, "h2", "texto"),
                ("D:/data/Jurisprudencia/fallo.pdf", "fallo.pdf", "Jurisprudencia", ".pdf", 300, 1, "h3", "texto"),
            ],
        )

    assert catalog.category_counts() == {"Doctrina": 2, "Jurisprudencia": 1}
    doctrina_documents = catalog.browse_documents(category="Doctrina")
    assert {item["name"] for item in doctrina_documents} == {"art1.pdf", "art2.pdf"}
