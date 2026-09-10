from __future__ import annotations

import json
import sys
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import parse_qs, urlparse

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from services.standards_service import StandardsService

HOST = "127.0.0.1"
PORT = 8514
SERVICE = StandardsService()

HTML = r'''<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>LexIA — Diccionario de Estándares</title>
<style>
body{font-family:system-ui,-apple-system,Segoe UI,Roboto,sans-serif;margin:0;background:#f5f7fa;color:#172033}
header{background:#101827;color:#fff;padding:18px 24px;font-size:20px;font-weight:700}
main{max-width:1280px;margin:0 auto;padding:20px}.panel{background:#fff;border:1px solid #dce2ea;border-radius:12px;padding:16px;margin-bottom:16px}
.grid{display:grid;grid-template-columns:2fr 1fr 1fr 1fr;gap:10px}.grid2{display:grid;grid-template-columns:1fr 1fr;gap:16px}
input,select,button{font:inherit;padding:9px 10px;border:1px solid #cfd6df;border-radius:8px;background:#fff}button{cursor:pointer;background:#174ea6;color:white;border-color:#174ea6}
.item{padding:14px 0;border-bottom:1px solid #e8edf3}.item:last-child{border-bottom:0}.meta{font-size:12px;color:#657084;margin-top:6px}.uid{font-family:ui-monospace,Consolas,monospace;font-size:11px;color:#7b8495}
.badge{display:inline-block;padding:2px 7px;border-radius:999px;background:#edf2f7;font-size:11px;margin-right:5px}.weak{background:#fff3cd}.strong{background:#fde2e2}
blockquote{margin:10px 0;padding:10px 12px;border-left:4px solid #c7d2e0;background:#f8fafc}.relation{padding:9px 0;border-bottom:1px solid #edf0f4}.hidden{display:none}
@media(max-width:850px){.grid{grid-template-columns:1fr 1fr}.grid2{grid-template-columns:1fr}}
</style>
</head>
<body>
<header>LexIA — Diccionario de Estándares Jurídicos</header>
<main>
<div class="panel">
  <div class="grid">
    <input id="q" placeholder="Buscar por texto jurídico…">
    <select id="court"><option value="">Todos los tribunales</option></select>
    <select id="speaker"><option value="">Todas las voces</option></select>
    <select id="treatment"><option value="">Todos los tratamientos</option></select>
    <input id="from" placeholder="Fecha desde">
    <input id="to" placeholder="Fecha hasta">
    <input id="tag" placeholder="Tag">
    <button id="search">Buscar</button>
  </div>
</div>
<div class="grid2">
  <section class="panel"><div id="summary"></div><div id="results"></div></section>
  <section class="panel"><div id="detail">Seleccioná un estándar.</div></section>
</div>
</main>
<script>
const $=id=>document.getElementById(id);
function esc(s){return String(s??'').replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]));}
async function get(url){const r=await fetch(url);if(!r.ok)throw new Error(await r.text());return r.json();}
function fill(sel, vals){for(const v of vals||[]){const o=document.createElement('option');o.value=v;o.textContent=v;sel.appendChild(o)}}
async function search(){
 const p=new URLSearchParams();
 [['q','q'],['court','court'],['speaker','speaker'],['treatment','treatment'],['from','from'],['to','to'],['tag','tag']].forEach(([id,k])=>{if($(id).value)p.set(k,$(id).value)});p.set('limit','100');
 const d=await get('/api/search?'+p);
 $('summary').innerHTML='<b>'+d.total+'</b> estándares';
 if(!$('court').dataset.loaded){fill($('court'),d.filters?.courts);fill($('speaker'),d.filters?.speakers);fill($('treatment'),d.filters?.treatments);$('court').dataset.loaded='1'}
 $('results').innerHTML=(d.items||[]).map(x=>`<div class="item" data-uid="${esc(x.standard_uid)}"><div><b>${esc(x.statement)}</b></div><div class="meta">${esc(x.court||'')} · ${esc(x.judgment_date||'')} · ${esc(x.speaker)} · ${esc(x.treatment)}</div><div class="uid">${esc(x.standard_uid)}</div></div>`).join('')||'<p>Sin resultados.</p>';
 document.querySelectorAll('.item').forEach(el=>el.onclick=()=>detail(el.dataset.uid));
}
async function detail(uid){
 const d=await get('/api/standard?uid='+encodeURIComponent(uid));
 if(!d){$('detail').textContent='No encontrado';return}
 let quotes=(d.quotes||[]).map(q=>`<blockquote>${esc(q.quote_text)}<div class="meta">pág. ${esc(q.page_start||'—')}${q.page_end&&q.page_end!==q.page_start?'–'+esc(q.page_end):''}</div></blockquote>`).join('');
 let rel=(d.relations||[]).map(r=>`<div class="relation"><span class="badge ${r.status==='proposed'?'weak':''}">${esc(r.relation_type)}</span><span class="badge">${esc(r.status)}</span><div>${esc(r.other?.statement||'')}</div><div class="meta">${esc(r.other?.document_name||'')} · ${esc(r.other?.speaker||'')}</div></div>`).join('')||'<p>Sin relaciones visibles.</p>';
 $('detail').innerHTML=`<h2>${esc(d.statement)}</h2><div class="meta">${esc(d.document_name)} · ${esc(d.court||'')} · ${esc(d.judgment_date||'')}</div><p><span class="badge">${esc(d.speaker)}</span><span class="badge">${esc(d.treatment)}</span></p><h3>Citas</h3>${quotes||'<p>Sin citas.</p>'}<h3>Relaciones</h3>${rel}<p><button onclick="graph('${esc(uid)}')">Ver grafo</button></p><div id="graph"></div>`;
}
async function graph(uid){const g=await get('/api/graph?uid='+encodeURIComponent(uid)+'&depth=2');$('graph').innerHTML='<h3>Grafo</h3>'+((g.edges||[]).map(e=>`<div class="relation"><b>${esc(e.relation_type)}</b> · ${esc(e.status)}<div class="uid">${esc(e.from)} → ${esc(e.to)}</div></div>`).join('')||'<p>Sin aristas visibles.</p>')}
$('search').onclick=search;$('q').addEventListener('keydown',e=>{if(e.key==='Enter')search()});search();
</script>
</body></html>'''


def _one(values: dict[str, list[str]], name: str, default: str = "") -> str:
    vals = values.get(name) or []
    return vals[0] if vals else default


class Handler(BaseHTTPRequestHandler):
    def _json(self, payload, status=200):
        raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self):
        parsed = urlparse(self.path)
        qs = parse_qs(parsed.query)
        try:
            if parsed.path == "/api/search":
                tags = [x for x in qs.get("tag", []) if x]
                return self._json(SERVICE.search(
                    text=_one(qs, "q"), tags=tags, court=_one(qs, "court"),
                    date_from=_one(qs, "from"), date_to=_one(qs, "to"),
                    speaker=_one(qs, "speaker"), treatment=_one(qs, "treatment"),
                    limit=int(_one(qs, "limit", "50") or 50),
                ))
            if parsed.path == "/api/standard":
                return self._json(SERVICE.get_standard(_one(qs, "uid")))
            if parsed.path == "/api/graph":
                return self._json(SERVICE.graph(_one(qs, "uid"), depth=int(_one(qs, "depth", "1") or 1)))
            if parsed.path == "/api/investigation":
                return self._json({"ok": True, "sources": SERVICE.investigation_sources(_one(qs, "q"), limit=int(_one(qs, "limit", "8") or 8))})
            if parsed.path in {"/", "/index.html"}:
                raw = HTML.encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(raw)))
                self.end_headers()
                return self.wfile.write(raw)
            self.send_error(404)
        except Exception as exc:
            self._json({"ok": False, "error": str(exc)}, 500)

    def log_message(self, fmt, *args):
        return


def main() -> int:
    if not SERVICE.available():
        raise SystemExit(f"No existe la base de estándares: {SERVICE.db_path}")
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"LexIA Diccionario de Estándares: http://{HOST}:{PORT}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
