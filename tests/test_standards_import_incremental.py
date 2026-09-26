import json
import sqlite3
from pathlib import Path

from tools.importar_estandares_sqlite import import_validated_run


ROOT = Path(__file__).resolve().parents[1]


def write_run(root: Path, statement: str) -> tuple[Path, Path]:
    prepared = root / "prepared"
    validated = root / "validated"
    prepared.mkdir(parents=True, exist_ok=True)
    validated.mkdir(parents=True, exist_ok=True)
    document = {
        "pilot_id": 1,
        "document_path": "/fallos/a.pdf",
        "document_name": "A.pdf",
        "metadata": {"court": "CSJN", "date": "2025-01-01"},
        "fragments": [],
    }
    (prepared / "fallos.jsonl").write_text(
        json.dumps(document, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    result = {
        "standards": [{
            "identifier": "E1",
            "statement": statement,
            "speaker": "mayoria",
            "source_speaker": "mayoria",
            "treatment": "adopta",
            "conditions": [],
            "consequence": None,
            "exceptions": [],
            "quotes": [{
                "unit_ids": ["C0001-U001"],
                "chunk_id": "C0001",
                "page_start": 1,
                "page_end": 1,
                "text": "cita literal",
                "validation": "resolved_from_unit_ids",
            }],
        }],
        "validation": {"issues": []},
    }
    (validated / "001_validado.json").write_text(
        json.dumps(result, ensure_ascii=False), encoding="utf-8"
    )
    return prepared / "fallos.jsonl", validated


def test_reextracting_document_hides_only_obsolete_automatic_standards(tmp_path):
    db = tmp_path / "standards.sqlite3"
    fallos, validated = write_run(tmp_path / "run1", "Regla original")
    first = import_validated_run(
        validated_dir=validated,
        fallos_path=fallos,
        db_path=db,
        schema_path=ROOT / "standards" / "schema.sql",
        run_id="run-1",
    )
    assert first["imported"]["superseded"] == 0
    con = sqlite3.connect(db)
    document_id = con.execute("SELECT document_id FROM documents").fetchone()[0]
    con.execute(
        """INSERT INTO standards(
               standard_uid,document_id,run_id,statement,speaker,source_speaker,treatment,
               source_fingerprint,review_status,publication_status
           ) VALUES('STD-MANUAL',?,NULL,'Regla manual','mayoria','mayoria','adopta',
                    'manual-fingerprint','validated','ready')""",
        (document_id,),
    )
    con.commit()
    con.close()

    fallos2, validated2 = write_run(tmp_path / "run2", "Regla corregida")
    second = import_validated_run(
        validated_dir=validated2,
        fallos_path=fallos2,
        db_path=db,
        schema_path=ROOT / "standards" / "schema.sql",
        run_id="run-2",
    )

    con = sqlite3.connect(db)
    rows = con.execute(
        "SELECT statement,publication_status FROM standards ORDER BY statement"
    ).fetchall()
    assert second["imported"]["superseded"] == 1
    assert rows == [
        ("Regla corregida", "ready"),
        ("Regla manual", "ready"),
        ("Regla original", "hidden"),
    ]


def test_reimporting_same_result_is_idempotent(tmp_path):
    db = tmp_path / "standards.sqlite3"
    fallos, validated = write_run(tmp_path / "run", "Regla estable")
    for run_id in ("run-1", "run-2"):
        result = import_validated_run(
            validated_dir=validated,
            fallos_path=fallos,
            db_path=db,
            schema_path=ROOT / "standards" / "schema.sql",
            run_id=run_id,
        )
    con = sqlite3.connect(db)
    assert result["imported"]["superseded"] == 0
    assert con.execute("SELECT COUNT(*) FROM standards").fetchone()[0] == 1
    assert con.execute("SELECT publication_status FROM standards").fetchone()[0] == "ready"
