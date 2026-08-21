import sqlite3
from pathlib import Path

from storage.catalog import DocumentCatalog


def test_pending_vector_counts_are_lightweight_and_complete(tmp_path):
    catalog = DocumentCatalog(tmp_path / "catalog.sqlite3")
    with sqlite3.connect(catalog.database_path) as connection:
        connection.executemany(
            """
            INSERT INTO documents (
                path, name, category, extension, size, modified_ns,
                content_hash, vector_indexed_hash, text_content, metadata_json
            ) VALUES (?, ?, 'Jurisprudencia', '.pdf', 1, 1, ?, ?, '', '{}')
            """,
            [
                ("pending.pdf", "pending.pdf", "hash-1", None),
                ("ready.pdf", "ready.pdf", "hash-2", "hash-2"),
            ],
        )
        connection.executemany(
            """
            INSERT INTO vector_relocations (
                content_hash, old_path, new_path, status
            ) VALUES (?, ?, ?, ?)
            """,
            [
                ("hash-1", "old-1.pdf", "pending.pdf", "pending"),
                ("hash-2", "old-2.pdf", "ready.pdf", "completed"),
            ],
        )

    assert catalog.pending_vector_document_count() == 1
    assert catalog.pending_vector_relocation_count() == 1


def test_preview_and_sidebar_expose_real_pending_work():
    root = Path(__file__).parents[1]
    ui = (root / "app" / "ui.py").read_text(encoding="utf-8-sig")
    autosync = (root / "services" / "autosync_service.py").read_text(
        encoding="utf-8-sig"
    )

    assert '"pending_vectors": pending_vectors' in autosync
    assert '"pending_vector_relocations": pending_vector_relocations' in autosync
    assert '"total_work": (' in autosync
    assert 'current_file=("" if path == "Completado" else str(path))' in autosync

    assert 'preview_total_work' in ui
    assert 'f"Vectores pendientes: {pending_vectors}' in ui
    assert 'or preview_total_work <= 0' in ui
    assert '"indexing": ("⚙️", "Indexando vectores")' in ui
    assert '"knowledge": ("🧠", "Actualizando Knowledge")' in ui
    assert 'text=f"Documento {sync_position}/{sync_total}"' in ui
    assert 'f"Faltan {sync_remaining} documento(s) en esta etapa."' in ui
