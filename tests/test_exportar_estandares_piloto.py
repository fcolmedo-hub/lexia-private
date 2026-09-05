import json
import sqlite3

from tools.exportar_estandares_piloto import export_documents, write_export


def _build_catalog(path):
    connection = sqlite3.connect(path)
    connection.executescript(
        """
        CREATE TABLE documents (
            path TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            category TEXT NOT NULL,
            text_content TEXT NOT NULL,
            metadata_json TEXT NOT NULL DEFAULT '{}',
            total_pages INTEGER,
            is_deleted INTEGER NOT NULL DEFAULT 0
        );
        CREATE TABLE fragments (
            document_path TEXT NOT NULL,
            fragment_index INTEGER NOT NULL,
            text_content TEXT NOT NULL,
            start_char INTEGER NOT NULL,
            end_char INTEGER NOT NULL,
            page_start INTEGER,
            page_end INTEGER,
            PRIMARY KEY (document_path, fragment_index)
        );
        """
    )
    connection.execute(
        """
        INSERT INTO documents(
            path, name, category, text_content, metadata_json, total_pages
        ) VALUES (?, ?, 'Jurisprudencia', ?, ?, 2)
        """,
        (
            "/fallos/a.pdf",
            "a.pdf",
            "x" * 600,
            json.dumps({"court": "Tribunal de prueba"}),
        ),
    )
    connection.executemany(
        """
        INSERT INTO fragments(
            document_path, fragment_index, text_content,
            start_char, end_char, page_start, page_end
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        [
            ("/fallos/a.pdf", 1, "segundo", 8, 15, 2, 2),
            ("/fallos/a.pdf", 0, "primero", 0, 7, 1, 1),
        ],
    )
    connection.commit()
    connection.close()


def test_exporta_todos_los_fragmentos_en_orden(tmp_path):
    catalog = tmp_path / "catalog.sqlite3"
    _build_catalog(catalog)

    documents = export_documents(catalog, limit=50)

    assert len(documents) == 1
    assert [f["fragment_index"] for f in documents[0].fragments] == [0, 1]
    assert [f["page_start"] for f in documents[0].fragments] == [1, 2]
    assert documents[0].fragments[0]["chunk_id"].endswith("::0")


def test_escribe_jsonl_y_manifest_sin_api(tmp_path):
    catalog = tmp_path / "catalog.sqlite3"
    _build_catalog(catalog)
    documents = export_documents(catalog, limit=50)

    output = tmp_path / "out"
    manifest = write_export(documents, "PROMPT", output)

    assert manifest["documents"] == 1
    assert manifest["fragments"] == 2
    assert (output / "fallos.jsonl").exists()
    assert (output / "prompts.jsonl").exists()
    assert (output / "manifest.json").exists()

    prompt_row = json.loads(
        (output / "prompts.jsonl").read_text(encoding="utf-8").splitlines()[0]
    )
    assert "[CHUNK /fallos/a.pdf::0" in prompt_row["prompt"]
    assert "primero" in prompt_row["prompt"]
    assert "segundo" in prompt_row["prompt"]
