from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INDEX = ROOT / "app" / "ui2" / "index.html"
BACKEND = ROOT / "app" / "ui2" / "backend.py"
SERVER = ROOT / "app" / "ui2" / "server.py"

HOME_START = "/* >>> LEXIA UI2 HOME SEARCH REDIRECT 3.1.3a */"
HOME_END = "/* <<< LEXIA UI2 HOME SEARCH REDIRECT 3.1.3a */"
HOME_MARK = "LEXIA_HOME_FILENAME_SEARCH_20260830"
COUNTER_MARK = "LEXIA_HOME_SEARCH_COUNTER_UI2_V2_20260830"
CONTEXT_MARK = "LEXIA_UI2_CONTEXT_COUNTER_20260830"

HOME_BLOCK = r'''<script>
/* >>> LEXIA UI2 HOME SEARCH REDIRECT 3.1.3a */
(function(){
  // LEXIA_HOME_FILENAME_SEARCH_20260830
  const homeInput=()=>document.getElementById('homeQuickSearchInput');

  function setSidebarSearch(){
    document.querySelectorAll('.nav button[data-route]').forEach(button=>{
      button.classList.toggle('active',button.dataset.route==='searchpage');
    });
  }

  function navigateToSearch(){
    if(window.lexiaUI2NavigateGlobal) window.lexiaUI2NavigateGlobal('searchpage');
    else if(window.lexiaUI2NavigateSafe) window.lexiaUI2NavigateSafe('searchpage');
    else if(window.lexiaUI2Navigate) window.lexiaUI2Navigate('searchpage');
    else if(window.lexiaUI2Show) window.lexiaUI2Show('searchpage');
    else{
      document.querySelectorAll('.page').forEach(page=>page.classList.remove('active'));
      document.getElementById('searchpage')?.classList.add('active');
    }
    setSidebarSearch();
  }

  function activateFilenameMode(){
    if(window.lexiaSearch320SetMode){
      window.lexiaSearch320SetMode('filename');
      return;
    }
    const tabs=[...document.querySelectorAll('#searchpage .search-modes .mode')];
    const filenameTab=tabs.find(button=>(button.textContent||'').toLocaleLowerCase('es-AR').includes('nombre'));
    filenameTab?.click();
  }

  function go(){
    const q=(homeInput()?.value||'').trim();
    if(!q)return;

    navigateToSearch();

    setTimeout(()=>{
      activateFilenameMode();
      setSidebarSearch();

      const legal=document.getElementById('legalQuery');
      if(legal){
        legal.value=q;
        legal.dispatchEvent(new Event('input',{bubbles:true}));
      }

      setTimeout(()=>{
        setSidebarSearch();
        if(window.lexiaSearch320Run) window.lexiaSearch320Run();
        else document.getElementById('runLegalSearch')?.click();
      },30);
    },50);
  }

  document.addEventListener('click',function(ev){
    const b=ev.target.closest('#homeQuickSearchButton');
    if(!b)return;
    ev.preventDefault();
    ev.stopPropagation();
    ev.stopImmediatePropagation();
    go();
  },true);

  document.addEventListener('keydown',function(ev){
    if(ev.key==='Enter' && document.activeElement===homeInput()){
      ev.preventDefault();
      ev.stopPropagation();
      ev.stopImmediatePropagation();
      go();
    }
  },true);
})();
/* <<< LEXIA UI2 HOME SEARCH REDIRECT 3.1.3a */
</script>'''

BACKEND_OLD = '''                # Prefer a table containing query/title/objective.
                selected = tables[0]
                selected_cols = []
                for table in tables:
                    cols = [r[1] for r in con.execute(f'PRAGMA table_info("{table}")').fetchall()]
                    lowered = {c.lower() for c in cols}
                    if {"query", "created_at"} & lowered or "query" in lowered:
                        selected, selected_cols = table, cols
                        break
'''

BACKEND_NEW = '''                # LEXIA_HOME_SEARCH_COUNTER_UI2_V2_20260830
                # search_history.sqlite3 conserva tablas históricas. Para el contador
                # visible de Inicio debe preferirse la tabla que UI2 actualiza hoy.
                selected = tables[0]
                selected_cols = []
                preferred_tables = []
                if path.name == "search_history.sqlite3":
                    preferred_tables.extend([
                        "ui2_search_history_v2",
                        "ui2_search_history",
                        "search_history",
                    ])
                preferred_tables.extend(tables)

                for table in preferred_tables:
                    if table not in tables:
                        continue
                    cols = [r[1] for r in con.execute(f'PRAGMA table_info("{table}")').fetchall()]
                    lowered = {c.lower() for c in cols}
                    if {"query", "created_at"} & lowered or "query" in lowered:
                        selected, selected_cols = table, cols
                        break
'''

SERVER_OLD = '''def _core_research_candidates_start(payload):
    response, _ = _delete_bridge_request("POST", "/api/research-candidates-start", payload)
    return response
'''

SERVER_NEW = r'''# LEXIA_UI2_CONTEXT_COUNTER_20260830
def _record_ui2_context_query_history(payload):
    """Registra una búsqueda de Investigación para el contador persistente de Inicio."""
    try:
        body = payload if isinstance(payload, dict) else {}
        query = str(body.get("query") or body.get("question") or body.get("prompt") or "").strip()
        if not query:
            return

        facts = str(body.get("facts") or body.get("antecedents") or body.get("antecedentes") or "").strip()
        objective = str(body.get("objective") or body.get("goal") or "Investigación jurídica").strip()
        instruction = str(body.get("additional_instruction") or body.get("instruction") or body.get("instructions") or "").strip()
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
                "query TEXT NOT NULL, facts TEXT, objective TEXT, "
                "additional_instruction TEXT, max_sources INTEGER, "
                "created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)"
            )
            cols = {
                str(row[1])
                for row in con.execute('PRAGMA table_info("context_query_history")').fetchall()
            }
            fields = ["query"]
            values = [query]
            optional = [
                ("facts", facts),
                ("objective", objective),
                ("additional_instruction", instruction),
                ("max_sources", max_sources),
            ]
            for name, value in optional:
                if name in cols:
                    fields.append(name)
                    values.append(value)

            quoted = ",".join('"' + name + '"' for name in fields)
            placeholders = ",".join("?" for _ in fields)
            if "created_at" in cols:
                quoted += ',"created_at"'
                placeholders += ",CURRENT_TIMESTAMP"
            con.execute(
                "INSERT INTO context_query_history (" + quoted + ") VALUES (" + placeholders + ")",
                values,
            )
            con.commit()
        finally:
            con.close()
    except Exception:
        # El contador nunca debe impedir una investigación.
        pass


def _core_research_candidates_start(payload):
    response, _ = _delete_bridge_request("POST", "/api/research-candidates-start", payload)
    # Contar únicamente el inicio de la búsqueda de candidatos. Crear el paquete
    # posterior no constituye una nueva búsqueda y no debe duplicar el contador.
    _record_ui2_context_query_history(payload)
    return response
'''


def patch_home() -> bool:
    text = INDEX.read_text(encoding="utf-8", errors="replace")
    if HOME_MARK in text:
        print("OK: búsqueda de Inicio ya estaba corregida")
        return False

    pattern = re.compile(
        r'<script>\s*' + re.escape(HOME_START) + r'.*?' + re.escape(HOME_END) + r'\s*</script>',
        re.S,
    )
    matches = list(pattern.finditer(text))
    if len(matches) != 1:
        raise SystemExit(
            f"ABORTADO: esperaba 1 bloque HOME SEARCH REDIRECT y encontré {len(matches)}. No modifiqué archivos."
        )

    old_block = matches[0].group(0)
    if "homeQuickSearchInput" not in old_block or "runLegalSearch" not in old_block:
        raise SystemExit("ABORTADO: el bloque de búsqueda de Inicio no tiene la estructura esperada.")

    backup = INDEX.with_suffix(".html.bak-home-filename-search")
    if not backup.exists():
        backup.write_text(text, encoding="utf-8")
    patched = text[:matches[0].start()] + HOME_BLOCK + text[matches[0].end():]
    INDEX.write_text(patched, encoding="utf-8")
    print("OK: Inicio ahora abre Buscar / Nombre de archivo y marca Buscar")
    return True


def patch_search_counter() -> bool:
    text = BACKEND.read_text(encoding="utf-8", errors="replace")
    if COUNTER_MARK in text:
        print("OK: contador de búsquedas ya prioriza UI2")
        return False
    if text.count(BACKEND_OLD) != 1:
        raise SystemExit("ABORTADO: backend.py no coincide con el bloque esperado. No modifiqué backend.py.")

    backup = BACKEND.with_suffix(".py.bak-home-search-counter-ui2-v2")
    if not backup.exists():
        backup.write_text(text, encoding="utf-8")
    BACKEND.write_text(text.replace(BACKEND_OLD, BACKEND_NEW, 1), encoding="utf-8")
    print("OK: Inicio leerá el contador desde ui2_search_history_v2")
    return True


def patch_context_counter() -> bool:
    text = SERVER.read_text(encoding="utf-8", errors="replace")
    if CONTEXT_MARK in text:
        print("OK: contador de búsquedas de contexto ya estaba corregido")
        return False
    if text.count(SERVER_OLD) != 1:
        raise SystemExit("ABORTADO: server.py no coincide con _core_research_candidates_start esperado. No modifiqué server.py.")

    backup = SERVER.with_suffix(".py.bak-context-counter")
    if not backup.exists():
        backup.write_text(text, encoding="utf-8")
    SERVER.write_text(text.replace(SERVER_OLD, SERVER_NEW, 1), encoding="utf-8")
    print("OK: cada nueva Investigación incrementará el contador de contexto una sola vez")
    return True


def main() -> None:
    for path in (INDEX, BACKEND, SERVER):
        if not path.exists():
            raise SystemExit(f"ABORTADO: no existe {path}")

    # Validar primero los tres destinos antes de escribir cualquiera.
    index_text = INDEX.read_text(encoding="utf-8", errors="replace")
    backend_text = BACKEND.read_text(encoding="utf-8", errors="replace")
    server_text = SERVER.read_text(encoding="utf-8", errors="replace")

    if HOME_MARK not in index_text:
        pattern = re.compile(
            r'<script>\s*' + re.escape(HOME_START) + r'.*?' + re.escape(HOME_END) + r'\s*</script>',
            re.S,
        )
        matches = list(pattern.finditer(index_text))
        if len(matches) != 1 or "runLegalSearch" not in matches[0].group(0):
            raise SystemExit("ABORTADO: no pude validar el bloque de búsqueda de Inicio. No modifiqué nada.")

    if COUNTER_MARK not in backend_text and backend_text.count(BACKEND_OLD) != 1:
        raise SystemExit("ABORTADO: no pude validar el bloque del contador en backend.py. No modifiqué nada.")

    if CONTEXT_MARK not in server_text and server_text.count(SERVER_OLD) != 1:
        raise SystemExit("ABORTADO: no pude validar el inicio de Investigación en server.py. No modifiqué nada.")

    patch_home()
    patch_search_counter()
    patch_context_counter()

    print()
    print("LISTO")
    print("1. Inicio -> búsqueda por Nombre de archivo")
    print("2. Al salir de Inicio queda marcado Buscar")
    print("3. Búsquedas lee la tabla activa de UI2")
    print("4. Cada nueva Investigación suma 1 al contador de contexto")
    print("No se modificó ningún bloque del visor Office.")


if __name__ == "__main__":
    main()
