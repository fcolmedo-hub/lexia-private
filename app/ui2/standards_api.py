from __future__ import annotations

import json
import os
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from services.standards_service import StandardsService

HOST = "127.0.0.1"
PORT = int(os.environ.get("LEXIA_STANDARDS_PORT", "8515"))
SERVICE = StandardsService()


def _one(values: dict[str, list[str]], name: str, default: str = "") -> str:
    items = values.get(name) or []
    return items[0] if items else default


class Handler(BaseHTTPRequestHandler):
    def _cors(self) -> None:
        self.send_header("Access-Control-Allow-Origin", "http://127.0.0.1:*" if False else "*")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
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
