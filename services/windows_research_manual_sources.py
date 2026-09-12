from __future__ import annotations

from dataclasses import replace
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import json
import sys
import threading

from config.settings import SETTINGS
from core.document_extractor import DocumentExtractor
from models.search_result import SearchResult


PORT = 8516
_ALLOWED_ORIGINS = {
    "http://127.0.0.1:8512",
    "http://localhost:8512",
}

_LOCK = threading.RLock()
_SERVER: ThreadingHTTPServer | None = None
_THREAD: threading.Thread | None = None
_MANUAL_SOURCES: dict[str, dict] = {}
_PATCHED_BUILDERS: set[int] = set()


def _path_key(path: str | Path) -> str:
    return str(Path(path).expanduser().resolve()).casefold()


def _category_from_path(path: Path, fallback: str = "") -> str:
    root = Path(SETTINGS.library_path).expanduser().resolve()
    resolved = path.expanduser().resolve()
    try:
        relative = resolved.relative_to(root)
    except ValueError:
        return str(fallback or "Sin categoría")
    if not relative.parts:
        return str(fallback or "Sin categoría")
    top = relative.parts[0].casefold()
    mapping = {
        "escritos": "Escritos",
        "doctrina": "Doctrina",
        "jurisprudencia": "Jurisprudencia",
        "fallos": "Jurisprudencia",
        "legislacion": "Legislación",
        "legislación": "Legislación",
    }
    return mapping.get(top, str(fallback or relative.parts[0] or "Sin categoría"))


def _validate_library_file(path_value: str) -> Path:
    root = Path(SETTINGS.library_path).expanduser().resolve()
    path = Path(str(path_value or "")).expanduser().resolve()
    try:
        path.relative_to(root)
    except ValueError as exc:
        raise PermissionError("El documento debe pertenecer a la biblioteca de LexIA.") from exc
    if not path.is_file():
        raise FileNotFoundError("El documento ya no existe en la biblioteca de LexIA.")
    return path


def _state_for(application, path: Path) -> dict:
    try:
        state = application.catalog.get_file_state(str(path)) or {}
    except Exception:
        state = {}
    return state if isinstance(state, dict) else {}


def _build_manual_source(application, path: Path) -> SearchResult:
    state = _state_for(application, path)
    text = str(state.get("text_content") or "").strip()
    total_pages = None
    if not text:
        extraction = DocumentExtractor().extract(path)
        text = str(extraction.text or "").strip()
        total_pages = extraction.total_pages
    if not text:
        raise RuntimeError("El documento no contiene texto utilizable.")

    category = _category_from_path(path, str(state.get("category") or ""))
    metadata = {
        "manual_source": "1",
        "court": str(state.get("court") or ""),
        "date": str(state.get("date") or ""),
    }
    return SearchResult(
        document_name=path.name,
        document_path=path,
        category=category,
        fragment_index=0,
        text=text,
        score=1.0,
        page_start=1 if total_pages else None,
        page_end=total_pages if total_pages and total_pages > 1 else None,
        metadata=metadata,
    )


def _public_source(source: SearchResult, selected: bool = True) -> dict:
    text = " ".join(str(source.text or "").split())
    return {
        "manual": True,
        "selected": bool(selected),
        "name": source.document_name,
        "path": str(source.document_path),
        "category": source.category,
        "page_label": source.page_label,
        "snippet": text[:900],
        "score": float(source.score or 0),
    }


def _sources_snapshot() -> list[dict]:
    with _LOCK:
        return [
            _public_source(item["source"], bool(item.get("selected", True)))
            for item in _MANUAL_SOURCES.values()
        ]


def _add_source(application, path_value: str) -> dict:
    path = _validate_library_file(path_value)
    key = _path_key(path)
    with _LOCK:
        existing = _MANUAL_SOURCES.get(key)
        if existing:
            existing["selected"] = True
            return _public_source(existing["source"], True)

    source = _build_manual_source(application, path)
    with _LOCK:
        _MANUAL_SOURCES[key] = {"source": source, "selected": True}
    return _public_source(source, True)


def _set_selected(path_value: str, selected: bool) -> dict:
    key = _path_key(_validate_library_file(path_value))
    with _LOCK:
        item = _MANUAL_SOURCES.get(key)
        if not item:
            raise KeyError("La fuente manual ya no está disponible.")
        item["selected"] = bool(selected)
        return _public_source(item["source"], bool(selected))


def _remove_source(path_value: str) -> None:
    key = _path_key(_validate_library_file(path_value))
    with _LOCK:
        _MANUAL_SOURCES.pop(key, None)


def clear_manual_sources() -> None:
    with _LOCK:
        _MANUAL_SOURCES.clear()


def _selected_manual_sources() -> list[SearchResult]:
    with _LOCK:
        return [
            item["source"]
            for item in _MANUAL_SOURCES.values()
            if bool(item.get("selected", True))
        ]


def _install_curate_extension(application) -> None:
    builder = application.context_builder
    marker = id(builder)
    if marker in _PATCHED_BUILDERS:
        return

    original = builder.curate_package

    def curate_with_manual_sources(package, selected_indices):
        curated = original(package, selected_indices)
        manual = _selected_manual_sources()
        if not manual:
            return curated

        combined = list(curated.sources)
        existing_paths = {
            str(source.document_path).casefold()
            for source in combined
        }
        for source in manual:
            key = str(source.document_path).casefold()
            if key in existing_paths:
                continue
            combined.append(source)
            existing_paths.add(key)

        if len(combined) == len(curated.sources):
            return curated

        content = builder._curate_source_section(
            curated.content,
            list(range(len(combined))),
            combined,
        )
        return replace(
            curated,
            content=content,
            sources=combined,
            character_count=len(content),
            selected_count=builder._document_source_count(combined),
            document_count=max(
                int(getattr(curated, "document_count", 0) or 0),
                builder._document_source_count(combined),
            ),
        )

    builder.curate_package = curate_with_manual_sources
    _PATCHED_BUILDERS.add(marker)


def _handler(application):
    class Handler(BaseHTTPRequestHandler):
        server_version = "LexIA-Windows-Research-Sources/1.0"

        def log_message(self, _format, *_args):
            return

        def _cors(self) -> None:
            origin = str(self.headers.get("Origin") or "")
            if origin in _ALLOWED_ORIGINS:
                self.send_header("Access-Control-Allow-Origin", origin)
                self.send_header("Vary", "Origin")
            self.send_header("Access-Control-Allow-Headers", "Content-Type")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
            self.send_header("Cache-Control", "no-store")

        def _json(self, payload: dict, status: int = 200) -> None:
            raw = json.dumps(payload, ensure_ascii=False, default=str).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(raw)))
            self._cors()
            self.end_headers()
            self.wfile.write(raw)

        def _body(self) -> dict:
            length = int(self.headers.get("Content-Length", "0") or 0)
            raw = self.rfile.read(length) if length else b"{}"
            value = json.loads(raw.decode("utf-8"))
            if not isinstance(value, dict):
                raise ValueError("La solicitud debe ser un objeto JSON.")
            return value

        def do_OPTIONS(self):
            self.send_response(204)
            self._cors()
            self.end_headers()

        def do_GET(self):
            if self.path == "/health":
                return self._json({"ok": True})
            if self.path == "/sources":
                return self._json({"ok": True, "sources": _sources_snapshot()})
            return self._json({"ok": False, "error": "Ruta no encontrada."}, 404)

        def do_POST(self):
            try:
                body = self._body()
                if self.path == "/add-source":
                    source = _add_source(application, str(body.get("path") or ""))
                    return self._json({"ok": True, "source": source, "sources": _sources_snapshot()})
                if self.path == "/set-selected":
                    source = _set_selected(
                        str(body.get("path") or ""),
                        bool(body.get("selected", True)),
                    )
                    return self._json({"ok": True, "source": source, "sources": _sources_snapshot()})
                if self.path == "/remove-source":
                    _remove_source(str(body.get("path") or ""))
                    return self._json({"ok": True, "sources": _sources_snapshot()})
                if self.path == "/clear":
                    clear_manual_sources()
                    return self._json({"ok": True, "sources": []})
                return self._json({"ok": False, "error": "Ruta no encontrada."}, 404)
            except PermissionError as error:
                return self._json({"ok": False, "error": str(error)}, 403)
            except FileNotFoundError as error:
                return self._json({"ok": False, "error": str(error)}, 404)
            except (KeyError, ValueError) as error:
                return self._json({"ok": False, "error": str(error)}, 409)
            except Exception as error:
                return self._json({"ok": False, "error": str(error)}, 500)

    return Handler


def start_windows_research_manual_sources(application, port: int = PORT) -> bool:
    global _SERVER, _THREAD
    if sys.platform != "win32":
        return False
    if _SERVER is not None:
        return True

    _install_curate_extension(application)
    clear_manual_sources()
    server = ThreadingHTTPServer(("127.0.0.1", int(port)), _handler(application))
    thread = threading.Thread(
        target=server.serve_forever,
        name="LexIA-Windows-Research-Sources",
        daemon=True,
    )
    thread.start()
    _SERVER = server
    _THREAD = thread
    return True


def stop_windows_research_manual_sources() -> None:
    global _SERVER, _THREAD
    server = _SERVER
    _SERVER = None
    if server is not None:
        try:
            server.shutdown()
        finally:
            server.server_close()
    thread = _THREAD
    _THREAD = None
    if thread is not None and thread.is_alive():
        thread.join(timeout=2.0)
    clear_manual_sources()
