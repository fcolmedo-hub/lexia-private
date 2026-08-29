from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SERVER = ROOT / "app" / "ui2" / "server.py"

HELPER_ANCHOR = '''def get_search():
    global SEARCH
    if SEARCH is None:
        SEARCH = SearchRuntime()
    return SEARCH
'''

HELPER = '''def get_search():
    global SEARCH
    if SEARCH is None:
        SEARCH = SearchRuntime()
    return SEARCH


def _record_ui2_search_history(query, category, result_count):
    """Best-effort write for the Inicio search counter.

    UI2's /api/search endpoint uses _content_search_v2 directly, not
    SearchRuntime.search(). Therefore the Inicio counter must be updated here
    after every successful search launched from Inicio or Buscar.
    """
    try:
        q = str(query or "").strip() or "[busqueda]"
        cat = str(category or "").strip() or None
        n = int(result_count or 0)
        db = RUNTIME_ROOT / "search_history.sqlite3"
        db.parent.mkdir(parents=True, exist_ok=True)
        con = sqlite3.connect(str(db), timeout=5)
        try:
            con.execute(
                "CREATE TABLE IF NOT EXISTS search_history ("
                "id INTEGER PRIMARY KEY AUTOINCREMENT, "
                "query TEXT NOT NULL, "
                "category TEXT, "
                "result_count INTEGER NOT NULL, "
                "created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP"
                ")"
            )
            con.execute(
                "INSERT INTO search_history (query, category, result_count) VALUES (?, ?, ?)",
                (q, cat, n),
            )
            con.commit()
        finally:
            con.close()
    except Exception:
        pass
'''

OLD_SEARCH_RETURN = '''            result = _content_search_v2(
                query=query,
                limit=limit,
                category=category,
                folder=folder,
                semantic_fallback=bool(body.get("semantic_fallback", False)),
            )
            return self._json(result)
'''

NEW_SEARCH_RETURN = '''            result = _content_search_v2(
                query=query,
                limit=limit,
                category=category,
                folder=folder,
                semantic_fallback=bool(body.get("semantic_fallback", False)),
            )
            # LEXIA_UI2_SEARCH_COUNTER_SERVER_20260829
            # /api/search no pasa por SearchRuntime.search(); registra aquí
            # toda búsqueda exitosa para que Inicio actualice su contador.
            try:
                result_count = int(
                    result.get("count", len(result.get("results") or []))
                    if isinstance(result, dict)
                    else 0
                )
                _record_ui2_search_history(query, category, result_count)
            except Exception:
                pass
            return self._json(result)
'''


def main() -> None:
    if not SERVER.exists():
        raise SystemExit(f"No existe {SERVER}")

    text = SERVER.read_text(encoding="utf-8", errors="replace")
    original = text

    if "LEXIA_UI2_SEARCH_COUNTER_SERVER_20260829" not in text:
        if OLD_SEARCH_RETURN not in text:
            raise SystemExit("No encontré el bloque /api/search esperado. No modifiqué server.py.")
        text = text.replace(OLD_SEARCH_RETURN, NEW_SEARCH_RETURN, 1)

    if "def _record_ui2_search_history" not in text:
        if HELPER_ANCHOR not in text:
            raise SystemExit("No encontré get_search(). No modifiqué server.py.")
        text = text.replace(HELPER_ANCHOR, HELPER, 1)

    if text == original:
        print("OK: server.py ya tenía el parche de contador UI2.")
        return

    backup = SERVER.with_suffix(".py.bak-ui2-search-counter-server")
    if not backup.exists():
        backup.write_text(original, encoding="utf-8")

    SERVER.write_text(text, encoding="utf-8")
    print("OK: parche aplicado en app/ui2/server.py")
    print(f"Backup: {backup}")


if __name__ == "__main__":
    main()
