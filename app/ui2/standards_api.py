from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import subprocess
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path, PurePosixPath
from urllib.parse import parse_qs, urlparse

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from config.settings import SETTINGS
from services.standards_service import StandardsService
from services.standards_canonicalizer import rebuild_canonical_groups

HOST = "127.0.0.1"
PORT = int(os.environ.get("LEXIA_STANDARDS_PORT", "8515"))
SERVICE = StandardsService()


def _one(values: dict[str, list[str]], name: str, default: str = "") -> str:
    items = values.get(name) or []
    return items[0] if items else default


def _candidate_document_paths(detail: dict) -> list[Path]:
    out: list[Path] = []
    raw = str(detail.get("document_path") or "").strip()
    name = str(detail.get("document_name") or "").strip()

    if raw:
        out.append(Path(raw).expanduser())
        normalized = raw.replace("\\", "/")
        lower = normalized.lower()
        marker = "/data_test/"
        if marker in lower:
            rel = normalized[lower.index(marker) + len(marker):]
            if rel:
                out.append(SETTINGS.library_path / PurePosixPath(rel))
                out.append(ROOT / "data_test" / PurePosixPath(rel))

    if name:
        out.append(SETTINGS.library_path / name)
        out.append(ROOT / "data_test" / name)

    seen: set[str] = set()
    unique: list[Path] = []
    for candidate in out:
        key = str(candidate)
        if key not in seen:
            seen.add(key)
            unique.append(candidate)
    return unique


def _resolve_document_path(detail: dict) -> Path | None:
    for candidate in _candidate_document_paths(detail):
        try:
            if candidate.is_file():
                return candidate.resolve()
        except OSError:
            pass

    name = str(detail.get("document_name") or "").strip()
    if not name or not SETTINGS.library_path.exists():
        return None
    try:
        return next((p.resolve() for p in SETTINGS.library_path.rglob(name) if p.is_file()), None)
    except OSError:
        return None


def _open_document(path: Path) -> None:
    if sys.platform == "darwin":
        subprocess.Popen(["/usr/bin/open", str(path)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    elif os.name == "nt":
        os.startfile(str(path))  # type: ignore[attr-defined]
    else:
        subprocess.Popen(["xdg-open", str(path)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def _manual_standard(payload: dict) -> dict:
    statement = str(payload.get("statement") or "").strip()
    document_name = str(payload.get("document_name") or "").strip()
    if not statement:
        raise ValueError("El texto del estándar es obligatorio.")
    if not document_name:
        raise ValueError("El documento fuente es obligatorio.")

    document_path = str(payload.get("document_path") or "").strip() or None
    court = str(payload.get("court") or "").strip() or None
    judgment_date = str(payload.get("judgment_date") or "").strip() or None
    speaker = str(payload.get("speaker") or "mayoria").strip() or "mayoria"
    source_speaker = str(payload.get("source_speaker") or speaker).strip() or speaker
    treatment = str(payload.get("treatment") or "adopta").strip() or "adopta"
    quote = str(payload.get("quote") or "").strip()
    page_raw = str(payload.get("page") or "").strip()
    try:
        page = int(page_raw) if page_raw else None
    except ValueError:
        page = None
    if page is not None and page <= 0:
        page = None
    citation_complete = bool(quote and page)
    tags = [str(x).strip() for x in (payload.get("tags") or []) if str(x).strip()]

    seed = "|".join([document_name, document_path or "", court or "", judgment_date or "", statement, quote])
    digest = hashlib.sha256(seed.encode("utf-8")).hexdigest()
    standard_uid = "STD-M-" + digest[:20]
    source_key = "manual:" + hashlib.sha256((document_path or document_name).encode("utf-8")).hexdigest()[:24]
    source_fingerprint = hashlib.sha256((statement + "\n" + quote).encode("utf-8")).hexdigest()

    db = SERVICE.db_path
    if not db.exists():
        raise FileNotFoundError(str(db))

    con = sqlite3.connect(db, timeout=5)
    try:
        con.execute("PRAGMA foreign_keys=ON")
        con.execute("BEGIN IMMEDIATE")
        con.execute(
            """INSERT INTO documents(source_key,document_name,document_path,court,judgment_date,metadata_json)
               VALUES(?,?,?,?,?,?)
               ON CONFLICT(source_key) DO UPDATE SET
                 document_name=excluded.document_name,
                 document_path=COALESCE(excluded.document_path,documents.document_path),
                 court=COALESCE(excluded.court,documents.court),
                 judgment_date=COALESCE(excluded.judgment_date,documents.judgment_date),
                 updated_at=CURRENT_TIMESTAMP""",
            (source_key, document_name, document_path, court, judgment_date, json.dumps({"manual": True}, ensure_ascii=False)),
        )
        document_id = int(con.execute("SELECT document_id FROM documents WHERE source_key=?", (source_key,)).fetchone()[0])
        exists = con.execute("SELECT standard_uid FROM standards WHERE standard_uid=?", (standard_uid,)).fetchone()
        if exists:
            raise ValueError("Ese estándar ya fue cargado.")

        con.execute(
            """INSERT INTO standards(
                 standard_uid,document_id,local_identifier,statement,speaker,source_speaker,treatment,
                 conditions_json,consequence,exceptions_json,source_fingerprint,review_status,publication_status
               ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                standard_uid, document_id, "MANUAL", statement, speaker, source_speaker, treatment,
                "[]", None, "[]", source_fingerprint,
                "validated" if citation_complete else "needs_review",
                "ready" if citation_complete else "blocked",
            ),
        )
        if quote:
            con.execute(
                """INSERT INTO quotes(standard_uid,evidence_index,page_start,page_end,unit_ids_json,quote_text,validation)
                   VALUES(?,?,?,?,?,?,?)""",
                (standard_uid, 0, page, page, "[]", quote, "manual_review"),
            )
        for tag in sorted(set(tags), key=str.casefold):
            con.execute("INSERT OR IGNORE INTO tags(name) VALUES(?)", (tag,))
            tag_id = int(con.execute("SELECT tag_id FROM tags WHERE name=?", (tag,)).fetchone()[0])
            con.execute("INSERT OR IGNORE INTO standard_tags(standard_uid,tag_id) VALUES(?,?)", (standard_uid, tag_id))
        con.execute(
            "INSERT INTO standards_fts(standard_uid,statement,conditions,consequence,exceptions) VALUES(?,?,?,?,?)",
            (standard_uid, statement, "", "", ""),
        )
        rebuild_canonical_groups(con)
        con.commit()
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()

    return {
        "ok": True,
        "standard_uid": standard_uid,
        "ai_linking": "pending_provider",
        "publication_status": "ready" if citation_complete else "blocked",
        "message": (
            "Estándar almacenado y listo para publicarse. La vinculación automática por IA queda pendiente."
            if citation_complete
            else "Estándar almacenado como reservado. Completá una cita literal con página antes de publicarlo."
        ),
    }


def _canonical_decision(payload: dict) -> dict:
    try:
        relation_id = int(payload.get("relation_id"))
    except (TypeError, ValueError):
        raise ValueError("La relación canónica es inválida.")
    decision = str(payload.get("decision") or "").strip().lower()
    if decision not in {"confirm", "reject"}:
        raise ValueError("La decisión debe ser confirm o reject.")

    con = sqlite3.connect(SERVICE.db_path, timeout=5)
    try:
        con.execute("PRAGMA foreign_keys=ON")
        con.execute("BEGIN IMMEDIATE")
        relation = con.execute(
            """SELECT relation_type,status FROM relations
               WHERE relation_id=?""",
            (relation_id,),
        ).fetchone()
        if relation is None or str(relation[0]) != "duplicate_of":
            raise ValueError("La equivalencia propuesta no existe.")
        if str(relation[1]) in {"confirmed", "rejected"}:
            raise ValueError("La equivalencia ya tiene una decisión definitiva.")
        status = "confirmed" if decision == "confirm" else "rejected"
        con.execute(
            "UPDATE relations SET status=? WHERE relation_id=?",
            (status, relation_id),
        )
        decisions_table = con.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='relation_decisions'"
        ).fetchone()
        if decisions_table:
            con.execute(
                """UPDATE relation_decisions
                   SET decision_status='reviewed',updated_at=CURRENT_TIMESTAMP
                   WHERE relation_id=?""",
                (relation_id,),
            )
        canonicalization = rebuild_canonical_groups(con)
        con.commit()
        return {
            "ok": True,
            "relation_id": relation_id,
            "status": status,
            "canonicalization": canonicalization,
        }
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()


def _ensure_publication_decisions_schema(con: sqlite3.Connection) -> None:
    con.execute(
        """CREATE TABLE IF NOT EXISTS standard_publication_decisions (
               decision_id INTEGER PRIMARY KEY,
               standard_uid TEXT NOT NULL REFERENCES standards(standard_uid) ON DELETE CASCADE,
               decision TEXT NOT NULL CHECK(decision IN ('publish','reserve','reject')),
               previous_review_status TEXT NOT NULL,
               previous_publication_status TEXT NOT NULL,
               new_review_status TEXT NOT NULL,
               new_publication_status TEXT NOT NULL,
               decided_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
           )"""
    )
    con.execute(
        """CREATE INDEX IF NOT EXISTS idx_publication_decisions_standard
           ON standard_publication_decisions(standard_uid, decided_at)"""
    )


def _ensure_citation_decisions_schema(con: sqlite3.Connection) -> None:
    con.execute(
        """CREATE TABLE IF NOT EXISTS standard_citation_decisions (
               citation_decision_id INTEGER PRIMARY KEY,
               standard_uid TEXT NOT NULL REFERENCES standards(standard_uid) ON DELETE CASCADE,
               quote_id INTEGER NOT NULL REFERENCES quotes(quote_id) ON DELETE CASCADE,
               quote_text TEXT NOT NULL,
               page_start INTEGER NOT NULL,
               page_end INTEGER NOT NULL,
               decided_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
           )"""
    )
    con.execute(
        """CREATE INDEX IF NOT EXISTS idx_citation_decisions_standard
           ON standard_citation_decisions(standard_uid, decided_at)"""
    )


def _has_publishable_citation(con: sqlite3.Connection, standard_uid: str) -> bool:
    return con.execute(
        """SELECT 1 FROM quotes
           WHERE standard_uid=?
             AND TRIM(quote_text)<>''
             AND page_start IS NOT NULL
             AND page_start>0
             AND (page_end IS NULL OR page_end>=page_start)
           LIMIT 1""",
        (standard_uid,),
    ).fetchone() is not None


def _standard_citation(payload: dict) -> dict:
    standard_uid = str(payload.get("standard_uid") or "").strip()
    quote = str(payload.get("quote") or "").strip()
    if not standard_uid:
        raise ValueError("El estándar reservado es inválido.")
    if not quote:
        raise ValueError("La cita literal es obligatoria.")

    try:
        page_start = int(str(payload.get("page_start") or "").strip())
    except (TypeError, ValueError):
        raise ValueError("La página inicial debe ser un número positivo.")
    if page_start <= 0:
        raise ValueError("La página inicial debe ser un número positivo.")

    page_end_raw = str(payload.get("page_end") or "").strip()
    try:
        page_end = int(page_end_raw) if page_end_raw else page_start
    except ValueError:
        raise ValueError("La página final debe ser un número positivo.")
    if page_end < page_start:
        raise ValueError("La página final no puede ser anterior a la inicial.")

    con = sqlite3.connect(SERVICE.db_path, timeout=5)
    try:
        con.execute("PRAGMA foreign_keys=ON")
        con.execute("BEGIN IMMEDIATE")
        current = con.execute(
            "SELECT review_status FROM standards WHERE standard_uid=?",
            (standard_uid,),
        ).fetchone()
        if current is None:
            raise ValueError("El estándar reservado no existe.")
        if str(current[0]) == "rejected":
            raise ValueError("No se puede completar la cita de un estándar rechazado.")

        existing = con.execute(
            """SELECT quote_id,evidence_index FROM quotes
               WHERE standard_uid=? AND validation='manual_review'
               ORDER BY quote_id DESC LIMIT 1""",
            (standard_uid,),
        ).fetchone()
        if existing:
            quote_id = int(existing[0])
            con.execute(
                """UPDATE quotes SET quote_text=?,page_start=?,page_end=?,
                          unit_ids_json='[]',validation='manual_review'
                   WHERE quote_id=?""",
                (quote, page_start, page_end, quote_id),
            )
        else:
            evidence_index = int(con.execute(
                "SELECT COALESCE(MAX(evidence_index),-1)+1 FROM quotes WHERE standard_uid=?",
                (standard_uid,),
            ).fetchone()[0])
            cursor = con.execute(
                """INSERT INTO quotes(
                       standard_uid,evidence_index,page_start,page_end,
                       unit_ids_json,quote_text,validation
                   ) VALUES(?,?,?,?,?,?,?)""",
                (standard_uid, evidence_index, page_start, page_end, "[]", quote, "manual_review"),
            )
            quote_id = int(cursor.lastrowid)

        _ensure_citation_decisions_schema(con)
        con.execute(
            """INSERT INTO standard_citation_decisions(
                   standard_uid,quote_id,quote_text,page_start,page_end
               ) VALUES(?,?,?,?,?)""",
            (standard_uid, quote_id, quote, page_start, page_end),
        )
        con.commit()
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()

    return {
        "ok": True,
        "standard_uid": standard_uid,
        "quote_id": quote_id,
        "publishable": True,
        "standard": SERVICE.get_reserved_standard(standard_uid),
    }


def _publication_decision(payload: dict) -> dict:
    standard_uid = str(payload.get("standard_uid") or "").strip()
    decision = str(payload.get("decision") or "").strip().lower()
    if not standard_uid:
        raise ValueError("El estándar reservado es inválido.")
    if decision not in {"publish", "reserve", "reject"}:
        raise ValueError("La decisión debe ser publish, reserve o reject.")

    con = sqlite3.connect(SERVICE.db_path, timeout=5)
    try:
        con.execute("PRAGMA foreign_keys=ON")
        con.execute("BEGIN IMMEDIATE")
        current = con.execute(
            """SELECT review_status,publication_status FROM standards
               WHERE standard_uid=?""",
            (standard_uid,),
        ).fetchone()
        if current is None:
            raise ValueError("El estándar reservado no existe.")
        previous_review, previous_publication = map(str, current)
        if previous_review == "rejected":
            raise ValueError("El estándar ya fue rechazado.")

        if decision == "publish":
            if not _has_publishable_citation(con, standard_uid):
                raise ValueError("No se puede publicar: falta una cita literal con página.")
            new_review, new_publication = "validated", "ready"
        elif decision == "reject":
            new_review, new_publication = "rejected", "hidden"
        else:
            new_review, new_publication = previous_review, previous_publication

        _ensure_publication_decisions_schema(con)
        con.execute(
            """UPDATE standards SET review_status=?,publication_status=?,
                      updated_at=CURRENT_TIMESTAMP
               WHERE standard_uid=?""",
            (new_review, new_publication, standard_uid),
        )
        con.execute(
            """INSERT INTO standard_publication_decisions(
                   standard_uid,decision,previous_review_status,
                   previous_publication_status,new_review_status,
                   new_publication_status
               ) VALUES(?,?,?,?,?,?)""",
            (
                standard_uid, decision, previous_review, previous_publication,
                new_review, new_publication,
            ),
        )
        canonicalization = rebuild_canonical_groups(con)
        con.commit()
        return {
            "ok": True,
            "standard_uid": standard_uid,
            "decision": decision,
            "review_status": new_review,
            "publication_status": new_publication,
            "canonicalization": canonicalization,
        }
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()


class Handler(BaseHTTPRequestHandler):
    def _cors(self) -> None:
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def _json(self, payload, status: int = 200) -> None:
        raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self._cors()
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_OPTIONS(self):
        self.send_response(204)
        self._cors()
        self.end_headers()

    def do_POST(self):
        parsed = urlparse(self.path)
        try:
            length = int(self.headers.get("Content-Length") or "0")
            raw = self.rfile.read(length) if length > 0 else b"{}"
            payload = json.loads(raw.decode("utf-8"))
            if parsed.path == "/api/manual-standard":
                return self._json(_manual_standard(payload))
            if parsed.path == "/api/canonical-decision":
                return self._json(_canonical_decision(payload))
            if parsed.path == "/api/publication-decision":
                return self._json(_publication_decision(payload))
            if parsed.path == "/api/standard-citation":
                return self._json(_standard_citation(payload))
            return self._json({"ok": False, "error": "not_found"}, 404)
        except ValueError as exc:
            return self._json({"ok": False, "error": str(exc)}, 400)
        except Exception as exc:
            return self._json({"ok": False, "error": str(exc)}, 500)

    def do_GET(self):
        parsed = urlparse(self.path)
        qs = parse_qs(parsed.query)
        try:
            if parsed.path == "/api/health":
                return self._json({
                    "ok": True,
                    "available": SERVICE.available(),
                    "db_path": str(SERVICE.db_path),
                })
            if parsed.path == "/api/stats":
                inventory = SERVICE.inventory()
                return self._json({
                    "ok": True,
                    "available": SERVICE.available(),
                    "standards": inventory["visible_canonical_standards"],
                    "canonical_standards": inventory["visible_canonical_standards"],
                    **inventory,
                })
            if parsed.path == "/api/search":
                tags = [value for value in qs.get("tag", []) if value]
                return self._json(SERVICE.search(
                    text=_one(qs, "q"),
                    tags=tags,
                    court=_one(qs, "court"),
                    date_from=_one(qs, "from"),
                    date_to=_one(qs, "to"),
                    speaker=_one(qs, "speaker"),
                    treatment=_one(qs, "treatment"),
                    limit=int(_one(qs, "limit", "50") or 50),
                    offset=int(_one(qs, "offset", "0") or 0),
                ))
            if parsed.path == "/api/reserved":
                return self._json(SERVICE.reserved_standards(
                    limit=int(_one(qs, "limit", "50") or 50),
                    offset=int(_one(qs, "offset", "0") or 0),
                ))
            if parsed.path == "/api/reserved-standard":
                return self._json(SERVICE.get_reserved_standard(_one(qs, "uid")))
            if parsed.path == "/api/standard":
                return self._json(SERVICE.get_standard(_one(qs, "uid")))
            if parsed.path == "/api/graph":
                return self._json(SERVICE.graph(
                    _one(qs, "uid"),
                    depth=int(_one(qs, "depth", "1") or 1),
                ))
            if parsed.path == "/api/open-document":
                uid = _one(qs, "uid").strip()
                detail = (
                    SERVICE.get_occurrence(uid)
                    or SERVICE.get_reserved_standard(uid)
                    or SERVICE.get_standard(uid)
                )
                if not detail:
                    return self._json({"ok": False, "error": "standard_not_found"}, 404)
                resolved = _resolve_document_path(detail)
                if resolved is None:
                    return self._json({
                        "ok": False,
                        "error": "document_not_found",
                        "document_name": detail.get("document_name"),
                        "stored_path": detail.get("document_path"),
                    }, 404)
                _open_document(resolved)
                return self._json({"ok": True, "path": str(resolved)})
            if parsed.path == "/api/investigation":
                return self._json({
                    "ok": True,
                    "sources": SERVICE.investigation_sources(
                        _one(qs, "q"),
                        limit=int(_one(qs, "limit", "8") or 8),
                    ),
                })
            return self._json({"ok": False, "error": "not_found"}, 404)
        except Exception as exc:
            return self._json({"ok": False, "error": str(exc)}, 500)

    def log_message(self, fmt, *args):
        return


def main() -> int:
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"LexIA Standards API: http://{HOST}:{PORT}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
