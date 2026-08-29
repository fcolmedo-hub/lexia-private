from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SERVER = ROOT / "app" / "ui2" / "server.py"

HELPER_ANCHOR = '''def _record_ui2_search_history(query: str, mode: str):
    value = str(query or "").strip()
    search_mode = str(mode or "").strip().lower()
    if not value or search_mode not in ("filename", "professional"):
        return
    project_root = Path(__file__).resolve().parents[2]
    db = RUNTIME_ROOT / "search_history.sqlite3"
    con = sqlite3.connect(str(db), timeout=5)
    try:
        con.execute(
            "CREATE TABLE IF NOT EXISTS ui2_search_history_v2 ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT, "
            "mode TEXT NOT NULL, query TEXT NOT NULL, "
            "created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)"
        )
        con.execute(
            "INSERT INTO ui2_search_history_v2(mode,query,created_at) "
            "VALUES (?,?,CURRENT_TIMESTAMP)",
            (search_mode, value),
        )
        con.commit()
    finally:
        con.close()
'''

HELPER = HELPER_ANCHOR + r'''


def _record_ui2_context_query_history(payload):
    """Best-effort write for the Inicio investigation/context counter.

    UI2 launches research through the classic-core bridge. In the current UI2
    flow the classic context_query_history table may not be updated, so Inicio
    keeps showing an old count. Record the research start here in the same table
    that LiveReadOnlyAdapter.snapshot() already reads as "contexts".
    """
    try:
        body = payload if isinstance(payload, dict) else {}
        query = str(
            body.get("query")
            or body.get("question")
            or body.get("prompt")
            or body.get("title")
            or ""
        ).strip()
        if not query:
            return
        facts = str(
            body.get("facts")
            or body.get("antecedents")
            or body.get("antecedentes")
            or body.get("context")
            or ""
        ).strip()
        objective = str(
            body.get("objective")
            or body.get("goal")
            or body.get("mode")
            or "Investigación jurídica"
        ).strip()
        instruction = str(
            body.get("additional_instruction")
            or body.get("instruction")
            or body.get("instructions")
            or ""
        ).strip()
        try:
            max_sources = int(body.get("max_sources") or body.get("limit") or 14)
        except Exception:
            max_sources = 14

        db = RUNTIME_ROOT / "context_query_history.sqlite3"
        db.parent.mkdir(parents=True, exist_ok=True)
        con = sqlite3.connect(str(db), timeout=5)
        try:
            con.execute(
                "CREATE TABLE IF NOT EXISTS context_query_history ("
                "id INTEGER PRIMARY KEY AUTOINCREMENT, "
                "query TEXT NOT NULL, "
                "facts TEXT, "
                "objective TEXT, "
                "additional_instruction TEXT, "
                "max_sources INTEGER, "
                "created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP"
                ")"
            )
            con.execute(
                "INSERT INTO context_query_history "
                "(query,facts,objective,additional_instruction,max_sources,created_at) "
                "VALUES (?,?,?,?,?,CURRENT_TIMESTAMP)",
                (query, facts, objective, instruction, max_sources),
            )
            con.commit()
        finally:
            con.close()
    except Exception:
        pass
'''

OLD_CORE_RESEARCH = '''def _core_research_start(payload):
    response, _ = _delete_bridge_request("POST", "/api/research-start", payload)
    return response
'''

NEW_CORE_RESEARCH = '''def _core_research_start(payload):
    response, _ = _delete_bridge_request("POST", "/api/research-start", payload)
    # LEXIA_UI2_RESEARCH_COUNTER_CONTEXT_20260829
    # Inicio cuenta runtime/context_query_history.sqlite3. Registrar aquí
    # cada investigación iniciada desde UI2 porque el flujo nuevo pasa por
    # el puente clásico y no siempre actualiza esa tabla.
    _record_ui2_context_query_history(payload)
    return response
'''

OLD_CORE_CANDIDATES = '''def _core_research_candidates_start(payload):
    response, _ = _delete_bridge_request("POST", "/api/research-candidates-start", payload)
    return response
'''

NEW_CORE_CANDIDATES = '''def _core_research_candidates_start(payload):
    response, _ = _delete_bridge_request("POST", "/api/research-candidates-start", payload)
    # LEXIA_UI2_RESEARCH_CANDIDATES_COUNTER_CONTEXT_20260829
    _record_ui2_context_query_history(payload)
    return response
'''

OLD_CORE_PACKAGE = '''def _core_research_package_start(payload):
    response, _ = _delete_bridge_request("POST", "/api/research-package-start", payload, timeout=30)
    return response
'''

NEW_CORE_PACKAGE = '''def _core_research_package_start(payload):
    response, _ = _delete_bridge_request("POST", "/api/research-package-start", payload, timeout=30)
    # LEXIA_UI2_RESEARCH_PACKAGE_COUNTER_CONTEXT_20260829
    _record_ui2_context_query_history(payload)
    return response
'''


def main() -> None:
    if not SERVER.exists():
        raise SystemExit(f"No existe {SERVER}")

    text = SERVER.read_text(encoding="utf-8", errors="replace")
    original = text

    if "def _record_ui2_context_query_history" not in text:
        if HELPER_ANCHOR not in text:
            raise SystemExit("No encontré _record_ui2_search_history(). No modifiqué server.py.")
        text = text.replace(HELPER_ANCHOR, HELPER, 1)

    replacements = [
        (OLD_CORE_RESEARCH, NEW_CORE_RESEARCH, "_core_research_start"),
        (OLD_CORE_CANDIDATES, NEW_CORE_CANDIDATES, "_core_research_candidates_start"),
        (OLD_CORE_PACKAGE, NEW_CORE_PACKAGE, "_core_research_package_start"),
    ]
    for old, new, label in replacements:
        if new in text:
            continue
        if old in text:
            text = text.replace(old, new, 1)
        elif label in text:
            print(f"AVISO: {label} existe pero no coincide con el bloque esperado; no se modificó ese bloque.")
        else:
            print(f"AVISO: no encontré {label}; continúo.")

    if text == original:
        print("OK: server.py ya tenía el parche de contador de investigación.")
        return

    backup = SERVER.with_suffix(".py.bak-research-counter-context")
    if not backup.exists():
        backup.write_text(original, encoding="utf-8")

    SERVER.write_text(text, encoding="utf-8")
    print("OK: parche aplicado en app/ui2/server.py")
    print(f"Backup: {backup}")


if __name__ == "__main__":
    main()
