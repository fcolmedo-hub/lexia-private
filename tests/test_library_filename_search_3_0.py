from pathlib import Path

from storage.catalog import DocumentCatalog


def _insert_document(
    catalog: DocumentCatalog,
    *,
    path: str,
    name: str,
    content_hash: str,
) -> None:
    with catalog._connect() as connection:
        connection.execute(
            """
            INSERT INTO documents (
                path, name, category, extension, size, modified_ns,
                content_hash, text_content, metadata_json
            ) VALUES (?, ?, 'Jurisprudencia', '.pdf', 100, 1, ?, '', '{}')
            """,
            (path, name, content_hash),
        )


def test_library_query_matches_filename_but_not_folder_path(tmp_path):
    catalog = DocumentCatalog(tmp_path / "catalog.sqlite3")
    path_only = (
        r"D:\LexIA_2.3_DEV\data_test\Jurisprudencia"
        r"\Carpeta Secreta\fallo_alberdi.pdf"
    )
    filename_match = (
        r"D:\LexIA_2.3_DEV\data_test\Jurisprudencia"
        r"\Otra Carpeta\Carpeta Secreta - resumen.pdf"
    )
    _insert_document(
        catalog,
        path=path_only,
        name="fallo_alberdi.pdf",
        content_hash="hash-path-only",
    )
    _insert_document(
        catalog,
        path=filename_match,
        name="Carpeta Secreta - resumen.pdf",
        content_hash="hash-filename",
    )

    results = catalog.browse_documents_multi(query="carpeta secreta")

    assert [item["path"] for item in results] == [filename_match]


def test_library_ui_labels_search_as_filename_only():
    ui = (Path(__file__).parents[1] / "app" / "ui.py").read_text(
        encoding="utf-8-sig"
    )
    assert '"Nombre del archivo"' in ui
    assert '"Nombre o parte de la ruta"' not in ui
