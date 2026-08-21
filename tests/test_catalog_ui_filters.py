from pathlib import Path

from storage.catalog import DocumentCatalog


def _insert(catalog: DocumentCatalog, path: Path, category: str) -> None:
    with catalog._connect() as connection:
        connection.execute(
            """
            INSERT INTO documents (
                path, name, category, extension, size, modified_ns,
                content_hash, text_content
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                str(path.resolve()),
                path.name,
                category,
                path.suffix.lower(),
                10,
                1,
                "hash-" + path.stem,
                "texto",
            ),
        )


def test_category_and_folder_filters(tmp_path):
    catalog = DocumentCatalog(tmp_path / "catalog.db")
    root = tmp_path / "data_test"
    first = root / "Jurisprudencia" / "02" / "fallo.pdf"
    second = root / "Doctrina" / "articulo.pdf"
    first.parent.mkdir(parents=True)
    second.parent.mkdir(parents=True)
    first.write_bytes(b"pdf")
    second.write_bytes(b"pdf")

    _insert(catalog, first, "Jurisprudencia")
    _insert(catalog, second, "Doctrina")

    assert catalog.category_counts() == {
        "Doctrina": 1,
        "Jurisprudencia": 1,
    }
    assert catalog.folder_counts()[str(first.parent.resolve())] == 1
    assert catalog.folder_counts()[str((root / "Jurisprudencia").resolve())] == 1

    by_category = catalog.browse_documents(category="Jurisprudencia")
    assert [item["name"] for item in by_category] == ["fallo.pdf"]

    by_folder = catalog.browse_documents(folder=root / "Jurisprudencia")
    assert [item["name"] for item in by_folder] == ["fallo.pdf"]

    exact = catalog.browse_documents(
        folder=root / "Jurisprudencia",
        include_subfolders=False,
    )
    assert exact == []
