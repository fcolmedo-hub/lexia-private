import sqlite3
from pathlib import Path
from types import SimpleNamespace

from ai.context_package_builder import ContextPackage, ContextPackageBuilder
from storage.catalog import DocumentCatalog


def test_recent_documents_are_ordered_by_catalog_update(tmp_path: Path):
    catalog = DocumentCatalog(tmp_path / "catalog.sqlite3")
    with sqlite3.connect(catalog.database_path) as connection:
        connection.executemany(
            """
            INSERT INTO documents (
                path, name, category, extension, size, modified_ns,
                content_hash, text_content, metadata_json, updated_at
            ) VALUES (?, ?, 'Jurisprudencia', '.pdf', 1, 1, ?, '', '{}', ?)
            """,
            [
                ("antiguo.pdf", "antiguo.pdf", "hash-1", "2026-01-01 10:00:00"),
                ("nuevo.pdf", "nuevo.pdf", "hash-2", "2026-08-09 20:00:00"),
            ],
        )

    rows = catalog.recent_documents(limit=10)
    assert [row["name"] for row in rows] == ["nuevo.pdf", "antiguo.pdf"]


def test_context_sources_can_be_curated_without_new_search():
    sources = [
        SimpleNamespace(document_name="A.pdf"),
        SimpleNamespace(document_name="B.pdf"),
        SimpleNamespace(document_name="C.pdf"),
    ]
    content = """Encabezado

FUENTES

[FUENTE 1]
Documento: A.pdf
Contenido: A

[FUENTE 2]
Documento: B.pdf
Contenido: B

[FUENTE 3]
Documento: C.pdf
Contenido: C

ESTRUCTURA DE LA RESPUESTA

1. Conclusión.
"""
    package = ContextPackage(
        title="prueba",
        content=content,
        sources=sources,
        created_at="2026-08-09T20:00:00",
        character_count=len(content),
        objective="Investigación jurídica",
        query="consulta",
        facts="",
        interpretation={},
        document_count=3,
        selected_count=3,
    )

    builder = ContextPackageBuilder.__new__(ContextPackageBuilder)
    curated = builder.curate_package(package, [0, 2])

    assert curated.sources == [sources[0], sources[2]]
    assert curated.selected_count == 2
    assert "Documento: A.pdf" in curated.content
    assert "Documento: B.pdf" not in curated.content
    assert "Documento: C.pdf" in curated.content
    assert "[FUENTE 3]" not in curated.content
    assert curated.content.index("Documento: A.pdf") < curated.content.index(
        "[FUENTE 2]\nDocumento: C.pdf"
    )


def test_idle_navigation_has_no_global_catalog_queries():
    root = Path(__file__).parents[1]
    ui = (root / "app" / "ui.py").read_text(encoding="utf-8-sig")
    catalog = (root / "storage" / "catalog.py").read_text(
        encoding="utf-8-sig"
    )
    activity = (root / "services" / "activity_center_service.py").read_text(
        encoding="utf-8-sig"
    )

    sidebar_start = ui.index("with st.sidebar:")
    sidebar_end = ui.index('if page == "Inicio":', sidebar_start)
    sidebar = ui[sidebar_start:sidebar_end]
    assert "app.catalog.stats()" not in sidebar
    assert "app.activity_center.snapshot(" not in sidebar
    assert "st.progress(" not in sidebar

    assert "_cached_catalog_stats(_catalog_revision())" in ui
    assert "_cached_category_counts(" in ui
    assert "_cached_folder_counts(" in ui
    assert 'library_folder_cache_version = "2.8"' in ui
    assert 'or not st.session_state.get("_library_folder_counts_cache")' in ui
    assert "st.session_state._library_folder_cache_version" in ui
    assert "app.catalog.recent_documents(" in ui
    assert 'elif page == "Actividad":' in ui
    assert 'run_every="2s"' in ui
    assert "app.context_builder.curate_package(" in ui
    assert '"Incluir todas"' in ui
    assert '"Descartar todas"' in ui

    assert "def recent_documents(" in catalog
    assert "idx_documents_active_updated" in catalog
    assert "ORDER BY datetime(updated_at)" not in activity
