from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SERVER = ROOT / "app" / "ui2" / "server.py"
INDEX = ROOT / "app" / "ui2" / "index.html"

SERVER_HELPER_MARK = "LEXIA_UI2_PERSISTENT_RESEARCH_HISTORY_20260830"
INDEX_MARK = "LEXIA_UI2_PERSISTENT_RESEARCH_HISTORY_FRONTEND_20260830"

SERVER_HELPER_ANCHOR = "def _record_ui2_search_history(query: str, mode: str):\n"
SERVER_ROUTE_ANCHOR = '''    def do_GET(self):\n        path = urlparse(self.path).path\n        if path == "/api/maintenance-live":\n'''

SERVER_HELPER = r'''# LEXIA_UI2_PERSISTENT_RESEARCH_HISTORY_20260830
def _research_history_items(limit: int = 12):
    """Read persisted Investigation drafts from context_query_history.sqlite3."""
    db = RUNTIME_ROOT / "context_query_history.sqlite3"
    if not db.exists():
        return []

    try:
        wanted = max(1, min(int(limit or 12), 50))
    except Exception:
        wanted = 12

    con = sqlite3.connect(str(db), timeout=5)
    con.row_factory = sqlite3.Row
    try:
        tables = {
            str(row[0])
            for row in con.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        if "context_query_history" not in tables:
            return []

        columns = {
            str(row[1])
            for row in con.execute(
                'PRAGMA table_info("context_query_history")'
            ).fetchall()
        }
        if "query" not in columns:
            return []

        select_columns = []
        for name in (
            "id",
            "query",
            "facts",
            "objective",
            "additional_instruction",
            "max_sources",
            "created_at",
        ):
            if name in columns:
                select_columns.append(name)

        order = "id DESC" if "id" in columns else (
            "created_at DESC" if "created_at" in columns else "rowid DESC"
        )
        rows = con.execute(
            "SELECT " + ",".join('"' + name + '"' for name in select_columns) +
            " FROM context_query_history "
            "WHERE TRIM(COALESCE(query,''))<>'' "
            "ORDER BY " + order + " LIMIT ?",
            (max(wanted * 8, 50),),
        ).fetchall()

        items = []
        seen = set()
        for row in rows:
            keys = set(row.keys())
            query = str(row["query"] or "").strip()
            facts = str(row["facts"] or "").strip() if "facts" in keys else ""
            objective = str(row["objective"] or "").strip() if "objective" in keys else ""
            instruction = (
                str(row["additional_instruction"] or "").strip()
                if "additional_instruction" in keys
                else ""
            )
            key = (query, facts, objective, instruction)
            if key in seen:
                continue
            seen.add(key)
            items.append({
                "researchQuery": query,
                "researchFacts": facts,
                "researchObjective": objective,
                "researchInstruction": instruction,
                "maxSources": (
                    int(row["max_sources"] or 0)
                    if "max_sources" in keys and row["max_sources"] is not None
                    else None
                ),
                "createdAt": (
                    str(row["created_at"] or "")
                    if "created_at" in keys
                    else ""
                ),
            })
            if len(items) >= wanted:
                break
        return items
    finally:
        con.close()


'''

SERVER_ROUTE = '''    def do_GET(self):\n        path = urlparse(self.path).path\n        if path == "/api/research-history":\n            try:\n                return self._json({"ok": True, "items": _research_history_items(12)})\n            except Exception as exc:\n                return self._json({"ok": False, "error": str(exc)}, 500)\n        if path == "/api/maintenance-live":\n'''

OLD_FRONTEND = r'''  function readResearchHistory(){try{return JSON.parse(localStorage.getItem('lexia.research.history')||'[]').filter(item=>item&&item.researchQuery);}catch(_){return [];}}
  function refreshResearchHistory(){const select=$('researchHistory');if(!select)return;const items=readResearchHistory();select.innerHTML='<option value="">Elegir una consulta anterior…</option>'+items.map((item,index)=>`<option value="${index}">${escapeHtml(item.researchQuery.slice(0,120))}</option>`).join('');}
  function rememberResearchDraft(){const draft=researchDraft(),key=JSON.stringify(draft);const items=readResearchHistory().filter(item=>JSON.stringify(item)!==key);items.unshift(draft);try{localStorage.setItem('lexia.research.history',JSON.stringify(items.slice(0,12)));}catch(_){}refreshResearchHistory();}
  $('researchHistory')?.addEventListener('change',event=>{if(event.target.value==='')return;const index=Number(event.target.value),item=readResearchHistory()[index];if(!Number.isInteger(index)||!item)return;for(const id of researchFields){const field=$(id);if(field)field.value=item[id]||'';}event.target.value='';});
  refreshResearchHistory();
'''

NEW_FRONTEND = r'''  /* LEXIA_UI2_PERSISTENT_RESEARCH_HISTORY_FRONTEND_20260830 */
  let researchHistoryItems=[];
  function readResearchHistory(){return researchHistoryItems;}
  function localResearchHistory(){try{return JSON.parse(localStorage.getItem('lexia.research.history')||'[]').filter(item=>item&&item.researchQuery);}catch(_){return [];}}
  function renderResearchHistory(){const select=$('researchHistory');if(!select)return;const items=readResearchHistory();select.innerHTML='<option value="">Elegir una consulta anterior…</option>'+items.map((item,index)=>`<option value="${index}">${escapeHtml(String(item.researchQuery||'').slice(0,120))}</option>`).join('');}
  async function refreshResearchHistory(){
    let items=localResearchHistory();
    try{
      const res=await fetch('/api/research-history',{cache:'no-store'});
      const data=await res.json().catch(()=>({}));
      if(res.ok&&data.ok&&Array.isArray(data.items)){
        const merged=[...data.items,...items];
        const seen=new Set();
        items=merged.filter(item=>{
          if(!item||!item.researchQuery)return false;
          const key=JSON.stringify([
            item.researchQuery||'',item.researchFacts||'',item.researchObjective||'',item.researchInstruction||''
          ]);
          if(seen.has(key))return false;
          seen.add(key);return true;
        }).slice(0,12);
      }
    }catch(_){}
    researchHistoryItems=items.slice(0,12);
    try{localStorage.setItem('lexia.research.history',JSON.stringify(researchHistoryItems));}catch(_){}
    renderResearchHistory();
  }
  function rememberResearchDraft(){
    const draft=researchDraft(),key=JSON.stringify(draft);
    const items=readResearchHistory().filter(item=>JSON.stringify(item)!==key);
    items.unshift(draft);
    researchHistoryItems=items.slice(0,12);
    try{localStorage.setItem('lexia.research.history',JSON.stringify(researchHistoryItems));}catch(_){}
    renderResearchHistory();
  }
  $('researchHistory')?.addEventListener('change',event=>{if(event.target.value==='')return;const index=Number(event.target.value),item=readResearchHistory()[index];if(!Number.isInteger(index)||!item)return;for(const id of researchFields){const field=$(id);if(field)field.value=item[id]||'';}event.target.value='';});
  refreshResearchHistory();
'''


def validate() -> tuple[str, str]:
    if not SERVER.exists() or not INDEX.exists():
        raise SystemExit("ABORTADO: no encontré app/ui2/server.py o app/ui2/index.html")

    server_text = SERVER.read_text(encoding="utf-8", errors="replace")
    index_text = INDEX.read_text(encoding="utf-8", errors="replace")

    if SERVER_HELPER_MARK not in server_text and SERVER_HELPER_ANCHOR not in server_text:
        raise SystemExit("ABORTADO: no encontré _record_ui2_search_history en server.py. No modifiqué nada.")

    if 'path == "/api/research-history"' not in server_text and SERVER_ROUTE_ANCHOR not in server_text:
        raise SystemExit("ABORTADO: no encontré el ancla do_GET/maintenance-live en server.py. No modifiqué nada.")

    if INDEX_MARK not in index_text and index_text.count(OLD_FRONTEND) != 1:
        raise SystemExit("ABORTADO: el historial actual de Investigación no coincide con el bloque esperado. No modifiqué nada.")

    return server_text, index_text


def patch_server(text: str) -> None:
    original = text

    if SERVER_HELPER_MARK not in text:
        text = text.replace(SERVER_HELPER_ANCHOR, SERVER_HELPER + SERVER_HELPER_ANCHOR, 1)

    if 'path == "/api/research-history"' not in text:
        text = text.replace(SERVER_ROUTE_ANCHOR, SERVER_ROUTE, 1)

    if text == original:
        print("OK: backend de historial persistente ya estaba aplicado")
        return

    backup = SERVER.with_suffix(".py.bak-persistent-research-history")
    if not backup.exists():
        backup.write_text(original, encoding="utf-8")
    SERVER.write_text(text, encoding="utf-8")
    print("OK: backend persistente agregado a server.py")


def patch_index(text: str) -> None:
    if INDEX_MARK in text:
        print("OK: frontend de historial persistente ya estaba aplicado")
        return

    backup = INDEX.with_suffix(".html.bak-persistent-research-history")
    if not backup.exists():
        backup.write_text(text, encoding="utf-8")
    INDEX.write_text(text.replace(OLD_FRONTEND, NEW_FRONTEND, 1), encoding="utf-8")
    print("OK: desplegable de Investigación reconstruido desde SQLite")


def main() -> None:
    server_text, index_text = validate()
    patch_server(server_text)
    patch_index(index_text)

    print()
    print("LISTO")
    print("Las Consultas recientes de Investigación ahora persisten al cerrar LexIA.")
    print("Se conservan hasta 12 consultas recientes y se reconstruyen desde SQLite al iniciar.")
    print("No se modificó el Buscador ni el visor Office.")


if __name__ == "__main__":
    main()
