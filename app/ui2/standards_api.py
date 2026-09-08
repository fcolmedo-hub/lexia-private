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
                "[]", None, "[]", source_fingerprint, "validated", "ready",
            ),
        )
        if quote:
            con.execute(
                """INSERT INTO quotes(standard_uid,evidence_index,page_start,page_end,unit_ids_json,quote_text,validation)
                   VALUES(?,?,?,?,?,?,?)""",
                (standard_uid, 0, page, page, "[]", quote, "manual"),
            )
        for tag in sorted(set(tags), key=str.casefold):
            con.execute("INSERT OR IGNORE INTO tags(name) VALUES(?)", (tag,))
            tag_id = int(con.execute("SELECT tag_id FROM tags WHERE name=?", (tag,)).fetchone()[0])
            con.execute("INSERT OR IGNORE INTO standard_tags(standard_uid,tag_id) VALUES(?,?)", (standard_uid, tag_id))
        con.execute(
            "INSERT INTO standards_fts(standard_uid,statement,conditions,consequence,exceptions) VALUES(?,?,?,?,?)",
            (standard_uid, statement, "", "", ""),
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
        "ai_linking": "pending_provider",
        "message": "Estándar cargado. La vinculación automática por IA queda pendiente hasta configurar el proveedor de IA de LexIA.",
    }


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
                return self._json({
                    "ok": True,
                    "available": SERVICE.available(),
                    "standards": SERVICE.count(),
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
            if parsed.path == "/api/standard":
                return self._json(SERVICE.get_standard(_one(qs, "uid")))
            if parsed.path == "/api/graph":
                return self._json(SERVICE.graph(
                    _one(qs, "uid"),
                    depth=int(_one(qs, "depth", "1") or 1),
                ))
            if parsed.path == "/api/open-document":
                uid = _one(qs, "uid").strip()
                detail = SERVICE.get_standard(uid)
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
