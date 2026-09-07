from __future__ import annotations

import argparse
import hashlib
import json
import re
import sqlite3
import uuid
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_FALLOS = REPO_ROOT / "runtime" / "standards_pilot" / "export_50_v5" / "fallos.jsonl"
DEFAULT_DB = REPO_ROOT / "runtime" / "standards" / "standards.sqlite3"
DEFAULT_SCHEMA = REPO_ROOT / "standards" / "schema.sql"


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as fh:
        for lineno, raw in enumerate(fh, start=1):
            raw = raw.strip()
            if not raw:
                continue
            value = json.loads(raw)
            if not isinstance(value, dict):
                raise RuntimeError(f"Registro no-objeto en {path}, línea {lineno}")
            rows.append(value)
    return rows


def json_compact(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def normalize_text(value: Any) -> str:
    text = str(value or "").strip().casefold()
    return re.sub(r"\s+", " ", text)


def first_metadata(metadata: dict[str, Any], keys: tuple[str, ...]) -> str | None:
    lower = {str(k).casefold(): v for k, v in metadata.items()}
    for key in keys:
        value = lower.get(key.casefold())
        if value not in (None, ""):
            return str(value)
    return None


def document_source_key(doc: dict[str, Any], pilot_id: int) -> str:
    path = str(doc.get("document_path") or "").strip()
    if path:
        return path
    name = str(doc.get("document_name") or "").strip()
    return f"pilot:{pilot_id}:{name}"


def standard_fingerprint(source_key: str, standard: dict[str, Any]) -> str:
    quotes = standard.get("quotes") if isinstance(standard.get("quotes"), list) else []
    evidence_units: list[list[str]] = []
    for quote in quotes:
        if not isinstance(quote, dict):
            continue
        unit_ids = quote.get("unit_ids") if isinstance(quote.get("unit_ids"), list) else []
        evidence_units.append([str(x) for x in unit_ids])
    payload = {
        "source_key": source_key,
        "statement": normalize_text(standard.get("statement")),
        "speaker": standard.get("speaker"),
        "source_speaker": standard.get("source_speaker"),
        "treatment": standard.get("treatment"),
        "evidence_units": evidence_units,
    }
    return hashlib.sha256(json_compact(payload).encode("utf-8")).hexdigest()


def standard_uid_from_fingerprint(fingerprint: str) -> str:
    return "STD-" + fingerprint[:24]


def ensure_schema(conn: sqlite3.Connection, schema_path: Path) -> None:
    conn.executescript(schema_path.read_text(encoding="utf-8"))


def upsert_document(conn: sqlite3.Connection, doc: dict[str, Any], pilot_id: int) -> tuple[int, str]:
    metadata = doc.get("metadata") if isinstance(doc.get("metadata"), dict) else {}
    source_key = document_source_key(doc, pilot_id)
    document_name = str(doc.get("document_name") or Path(str(doc.get("document_path") or "")).name or f"pilot-{pilot_id:03d}")
    court = first_metadata(metadata, ("court", "tribunal"))
    judgment_date = first_metadata(metadata, ("date", "fecha"))
    conn.execute(
        """
        INSERT INTO documents(source_key, document_name, document_path, pilot_id, court, judgment_date, metadata_json)
        VALUES(?,?,?,?,?,?,?)
        ON CONFLICT(source_key) DO UPDATE SET
            document_name=excluded.document_name,
            document_path=excluded.document_path,
            pilot_id=excluded.pilot_id,
            court=excluded.court,
            judgment_date=excluded.judgment_date,
            metadata_json=excluded.metadata_json,
            updated_at=CURRENT_TIMESTAMP
        """,
        (
            source_key,
            document_name,
            doc.get("document_path"),
            pilot_id,
            court,
            judgment_date,
            json_compact(metadata),
        ),
    )
    row = conn.execute("SELECT document_id FROM documents WHERE source_key=?", (source_key,)).fetchone()
    if row is None:
        raise RuntimeError(f"No se pudo resolver document_id para {source_key}")
    return int(row[0]), source_key


def standard_has_issue(issues: list[dict[str, Any]], standard_index: int) -> bool:
    return any(isinstance(issue, dict) and int(issue.get("standard", -1)) == standard_index for issue in issues)


def refresh_fts(conn: sqlite3.Connection, standard_uid: str, standard: dict[str, Any]) -> None:
    conditions = standard.get("conditions") if isinstance(standard.get("conditions"), list) else []
    exceptions = standard.get("exceptions") if isinstance(standard.get("exceptions"), list) else []
    conn.execute("DELETE FROM standards_fts WHERE standard_uid=?", (standard_uid,))
    conn.execute(
        "INSERT INTO standards_fts(standard_uid, statement, conditions, consequence, exceptions) VALUES(?,?,?,?,?)",
        (
            standard_uid,
            str(standard.get("statement") or ""),
            " | ".join(str(x) for x in conditions),
            str(standard.get("consequence") or ""),
            " | ".join(str(x) for x in exceptions),
        ),
    )


def import_validated_document(
    conn: sqlite3.Connection,
    doc: dict[str, Any],
    pilot_id: int,
    result: dict[str, Any],
    run_id: str,
) -> dict[str, int]:
    document_id, source_key = upsert_document(conn, doc, pilot_id)
    validation = result.get("validation") if isinstance(result.get("validation"), dict) else {}
    issues = validation.get("issues") if isinstance(validation.get("issues"), list) else []
    standards = result.get("standards") if isinstance(result.get("standards"), list) else []

    imported = 0
    ready = 0
    blocked = 0
    quotes_count = 0

    for index, standard in enumerate(standards, start=1):
        if not isinstance(standard, dict):
            continue
        fingerprint = standard_fingerprint(source_key, standard)
        standard_uid = standard_uid_from_fingerprint(fingerprint)
        has_issue = standard_has_issue(issues, index)
        review_status = "needs_review" if has_issue else "validated"
        publication_status = "blocked" if has_issue else "ready"
        conditions = standard.get("conditions") if isinstance(standard.get("conditions"), list) else []
        exceptions = standard.get("exceptions") if isinstance(standard.get("exceptions"), list) else []

        conn.execute(
            """
            INSERT INTO standards(
                standard_uid, document_id, run_id, local_identifier, statement,
                speaker, source_speaker, treatment, conditions_json, consequence,
                exceptions_json, source_fingerprint, review_status, publication_status
            ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(standard_uid) DO UPDATE SET
                document_id=excluded.document_id,
                run_id=excluded.run_id,
                local_identifier=excluded.local_identifier,
                statement=excluded.statement,
                speaker=excluded.speaker,
                source_speaker=excluded.source_speaker,
                treatment=excluded.treatment,
                conditions_json=excluded.conditions_json,
                consequence=excluded.consequence,
                exceptions_json=excluded.exceptions_json,
                source_fingerprint=excluded.source_fingerprint,
                review_status=excluded.review_status,
                publication_status=CASE
                    WHEN standards.publication_status='published' AND excluded.review_status='validated' THEN 'published'
                    ELSE excluded.publication_status
                END,
                updated_at=CURRENT_TIMESTAMP
            """,
            (
                standard_uid,
                document_id,
                run_id,
                standard.get("identifier"),
                str(standard.get("statement") or "").strip(),
                str(standard.get("speaker") or ""),
                str(standard.get("source_speaker") or ""),
                str(standard.get("treatment") or ""),
                json_compact(conditions),
                standard.get("consequence"),
                json_compact(exceptions),
                fingerprint,
                review_status,
                publication_status,
            ),
        )

        conn.execute("DELETE FROM quotes WHERE standard_uid=?", (standard_uid,))
        quotes = standard.get("quotes") if isinstance(standard.get("quotes"), list) else []
        for q_index, quote in enumerate(quotes, start=1):
            if not isinstance(quote, dict):
                continue
            conn.execute(
                """
                INSERT INTO quotes(
                    standard_uid, evidence_index, chunk_id, page_start, page_end,
                    unit_ids_json, quote_text, validation
                ) VALUES(?,?,?,?,?,?,?,?)
                """,
                (
                    standard_uid,
                    q_index,
                    quote.get("chunk_id"),
                    quote.get("page_start"),
                    quote.get("page_end"),
                    json_compact(quote.get("unit_ids") if isinstance(quote.get("unit_ids"), list) else []),
                    str(quote.get("text") or ""),
                    str(quote.get("validation") or ""),
                ),
            )
            quotes_count += 1

        refresh_fts(conn, standard_uid, standard)
        imported += 1
        if has_issue:
            blocked += 1
        else:
            ready += 1

    return {"standards": imported, "ready": ready, "blocked": blocked, "quotes": quotes_count}


def main() -> int:
    parser = argparse.ArgumentParser(description="Importa resultados validados v5 a la base persistente de estándares.")
    parser.add_argument("--validated", type=Path, required=True, help="Carpeta validated_v5 con *_validado.json")
    parser.add_argument("--fallos", type=Path, default=DEFAULT_FALLOS)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA)
    parser.add_argument("--run-id", default=None)
    parser.add_argument("--model", default="gpt-5.6-luna")
    parser.add_argument("--reasoning-effort", default="medium")
    args = parser.parse_args()

    if not args.validated.exists():
        parser.error(f"No existe carpeta validada: {args.validated}")
    if not args.fallos.exists():
        parser.error(f"No existe fallos.jsonl: {args.fallos}")
    if not args.schema.exists():
        parser.error(f"No existe schema.sql: {args.schema}")

    docs = load_jsonl(args.fallos)
    by_id = {int(row.get("pilot_id")): row for row in docs if row.get("pilot_id") is not None}
    files = sorted(args.validated.glob("*_validado.json"))
    if not files:
        parser.error(f"No hay *_validado.json en {args.validated}")

    run_id = args.run_id or f"v5-{uuid.uuid4().hex[:12]}"
    args.db.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(args.db)
    try:
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA journal_mode=WAL")
        ensure_schema(conn, args.schema)
        conn.execute(
            """
            INSERT OR IGNORE INTO extraction_runs(
                run_id, extractor_version, model, reasoning_effort, source_dir, notes
            ) VALUES(?,?,?,?,?,?)
            """,
            (run_id, "v5", args.model, args.reasoning_effort, str(args.validated.resolve()), "evidence_mode=deterministic_unit_ids"),
        )

        totals = {"documents": 0, "standards": 0, "ready": 0, "blocked": 0, "quotes": 0}
        with conn:
            for path in files:
                try:
                    pilot_id = int(path.name.split("_", 1)[0])
                except ValueError:
                    continue
                doc = by_id.get(pilot_id)
                if doc is None:
                    raise RuntimeError(f"pilot_id {pilot_id} no existe en {args.fallos}")
                result = json.loads(path.read_text(encoding="utf-8"))
                stats = import_validated_document(conn, doc, pilot_id, result, run_id)
                totals["documents"] += 1
                for key in ("standards", "ready", "blocked", "quotes"):
                    totals[key] += stats[key]
                print(
                    f"{path.name}: estándares={stats['standards']}, ready={stats['ready']}, "
                    f"blocked={stats['blocked']}, citas={stats['quotes']}"
                )

        db_counts = {
            "documents": conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0],
            "standards": conn.execute("SELECT COUNT(*) FROM standards").fetchone()[0],
            "quotes": conn.execute("SELECT COUNT(*) FROM quotes").fetchone()[0],
            "ready": conn.execute("SELECT COUNT(*) FROM standards WHERE publication_status='ready'").fetchone()[0],
            "blocked": conn.execute("SELECT COUNT(*) FROM standards WHERE publication_status='blocked'").fetchone()[0],
        }
        print(json.dumps({
            "run_id": run_id,
            "imported": totals,
            "database": db_counts,
            "db_path": str(args.db.resolve()),
        }, ensure_ascii=False, indent=2))
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
