import json
import sqlite3
from pathlib import Path

import pytest

from services.standards_pipeline import StandardsPipeline


ROOT = Path(__file__).resolve().parents[1]


def make_catalog(tmp_path: Path) -> tuple[Path, Path]:
    document = (tmp_path / "fallo.pdf").resolve()
    catalog = tmp_path / "catalog.sqlite3"
    con = sqlite3.connect(catalog)
    con.executescript(
        """
        CREATE TABLE documents(
            path TEXT PRIMARY KEY,name TEXT,category TEXT,text_content TEXT,
            metadata_json TEXT,total_pages INTEGER,is_deleted INTEGER DEFAULT 0
        );
        CREATE TABLE fragments(
            document_path TEXT,fragment_index INTEGER,text_content TEXT,
            start_char INTEGER,end_char INTEGER,page_start INTEGER,page_end INTEGER
        );
        """
    )
    text = "La ley tributaria exige reserva legal. " * 20
    con.execute(
        "INSERT INTO documents VALUES(?,?,?,?,?,?,0)",
        (str(document), document.name, "Jurisprudencia", text, json.dumps({"court": "CSJN"}), 1),
    )
    con.execute(
        "INSERT INTO fragments VALUES(?,?,?,?,?,?,?)",
        (str(document), 0, text, 0, len(text), 1, 1),
    )
    con.commit()
    con.close()
    selection = tmp_path / "seleccion.txt"
    selection.write_text(str(document) + "\n", encoding="utf-8")
    return catalog, selection


def test_prepare_creates_resumable_v5_run_without_api(tmp_path):
    catalog, selection = make_catalog(tmp_path)
    pipeline = StandardsPipeline(
        repo_root=ROOT,
        db_path=tmp_path / "standards.sqlite3",
        runs_root=tmp_path / "runs",
        run_id="run-test",
    )

    state = pipeline.prepare(
        catalog_path=catalog,
        paths_file=selection,
        model="test-model",
        reasoning_effort="medium",
    )

    assert state["stage"] == "extraction_ready_to_submit"
    assert state["documents"] == 1
    assert state["units"] > 0
    assert (pipeline.run_dir / "prepared_v5" / "fallos.jsonl").exists()
    assert (pipeline.run_dir / "extraction_batch" / "batch_input.jsonl").exists()
    assert pipeline.summary()["state"]["run_id"] == "run-test"


def test_prepare_refuses_legacy_relations_without_decision_history(tmp_path):
    catalog, selection = make_catalog(tmp_path)
    db = tmp_path / "standards.sqlite3"
    con = sqlite3.connect(db)
    con.execute(
        "CREATE TABLE relations(relation_id INTEGER PRIMARY KEY, status TEXT)"
    )
    con.execute("INSERT INTO relations(status) VALUES('proposed')")
    con.commit()
    con.close()
    pipeline = StandardsPipeline(
        repo_root=ROOT,
        db_path=db,
        runs_root=tmp_path / "runs",
        run_id="run-legacy",
    )

    with pytest.raises(RuntimeError, match="relation_decisions"):
        pipeline.prepare(
            catalog_path=catalog,
            paths_file=selection,
            model="test-model",
            reasoning_effort="medium",
        )


def test_prepare_refuses_already_imported_content_before_creating_run(tmp_path):
    catalog, selection = make_catalog(tmp_path)
    with sqlite3.connect(catalog) as connection:
        connection.execute("ALTER TABLE documents ADD COLUMN content_hash TEXT")
        connection.execute("UPDATE documents SET content_hash=?", ("a" * 64,))
    db = tmp_path / "standards.sqlite3"
    with sqlite3.connect(db) as connection:
        connection.execute("CREATE TABLE documents(document_path TEXT, source_key TEXT)")
        connection.execute("INSERT INTO documents VALUES(?,?)", (
            "/Volumes/otro/fallo.pdf", "sha256:" + "a" * 64
        ))
    pipeline = StandardsPipeline(repo_root=ROOT, db_path=db, runs_root=tmp_path / "runs", run_id="repeated")
    with pytest.raises(RuntimeError, match="ya importados"):
        pipeline.prepare(catalog_path=catalog, paths_file=selection,
                         model="test-model", reasoning_effort="medium")
    assert not pipeline.run_dir.exists()
