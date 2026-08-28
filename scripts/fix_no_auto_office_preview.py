from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SERVER = ROOT / "app" / "ui2" / "server.py"
INDEX = ROOT / "app" / "ui2" / "index.html"

OFFICE_PAGE_OLD = '''        if path == "/api/office-preview-page":
            try:
                query = parse_qs(urlparse(self.path).query)
                requested = str((query.get("path") or [""])[0] or "").strip()
                snippet = str((query.get("snippet") or [""])[0] or "")
                fallback = str((query.get("fallback") or [""])[0] or "").strip()

                if not requested:
                    return self._json({"ok": False, "error": "Falta path"}, 400)

                pdf_path = _office_preview_pdf(requested)
                actual_page = _best_office_preview_page(
                    pdf_path,
                    snippet,
                    fallback_page=fallback,
                )

                return self._json({
                    "ok": True,
                    "page": int(actual_page or 1),
                    "fallback_page": int(fallback) if fallback.isdigit() else None,
                })
            except FileNotFoundError as exc:
                return self._json({"ok": False, "error": str(exc)}, 503)
            except (ValueError, PermissionError) as exc:
                return self._json({"ok": False, "error": str(exc)}, 400)
            except Exception as exc:
                return self._json({"ok": False, "error": str(exc)}, 500)
'''

OFFICE_PAGE_NEW = '''        if path == "/api/office-preview-page":
            try:
                query = parse_qs(urlparse(self.path).query)
                requested = str((query.get("path") or [""])[0] or "").strip()
                snippet = str((query.get("snippet") or [""])[0] or "")
                fallback = str((query.get("fallback") or [""])[0] or "").strip()
                convert = str((query.get("convert") or [""])[0] or "").strip().lower()

                if not requested:
                    return self._json({"ok": False, "error": "Falta path"}, 400)

                # Llamadas automáticas desde búsqueda/listado: NO convertir Office.
                # Devolver 0 para que el frontend no pise la página real del resultado.
                if convert not in {"1", "true", "yes", "si", "sí"}:
                    return self._json({
                        "ok": True,
                        "page": int(fallback) if fallback.isdigit() else 0,
                        "fallback_page": int(fallback) if fallback.isdigit() else None,
                        "converted": False,
                        "reason": "office-preview-page-no-auto-convert",
                    })

                pdf_path = _office_preview_pdf(requested)
                actual_page = _best_office_preview_page(
                    pdf_path,
                    snippet,
                    fallback_page=fallback,
                )

                return self._json({
                    "ok": True,
                    "page": int(actual_page or 1),
                    "fallback_page": int(fallback) if fallback.isdigit() else None,
                    "converted": True,
                })
            except FileNotFoundError as exc:
                return self._json({"ok": False, "error": str(exc)}, 503)
            except (ValueError, PermissionError) as exc:
                return self._json({"ok": False, "error": str(exc)}, 400)
            except Exception as exc:
                return self._json({"ok": False, "error": str(exc)}, 500)
'''

INDEX_OLD = "window.lexiaQuickViewerOpen(path,previewPage||sourcePage,snippet);"
INDEX_NEW = "window.lexiaQuickViewerOpen(path,(previewPage&&previewPage>1?previewPage:sourcePage)||1,snippet);"

MARKERS = [
    "LEXIA_OFFICE_PREVIEW_PAGE_HASH_FIX_20260828",
    "LEXIA_OFFICE_PREVIEW_FORCE_PAGE_20260828B",
    "LEXIA_OFFICE_PREVIEW_CLICK_LOCATOR_20260828C",
    "LEXIA_OFFICE_PREVIEW_SINGLE_VIEWER_20260828D",
]

SINGLE_VIEWER_MARKER = "LEXIA_OFFICE_PREVIEW_SINGLE_VIEWER_20260828D"
SINGLE_VIEWER_SCRIPT = f'''
<script id="{SINGLE_VIEWER_MARKER}">
(function(){{
  'use strict';
  if(window.__LEXIA_OFFICE_PREVIEW_SINGLE_VIEWER_20260828D)return;
  window.__LEXIA_OFFICE_PREVIEW_SINGLE_VIEWER_20260828D=true;

  function isOffice(path){{
    return /\.(doc|docx|rtf|odt)$/i.test(String(path||'').split('?')[0].split('#')[0]);
  }}
  function decode(value){{
    try{{return decodeURIComponent(String(value||''));}}catch(_){{return String(value||'');}}
  }}
  function esc(value){{
    return String(value||'').replace(/[&<>"']/g,function(c){{return {{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}}[c];}});
  }}
  function officePdfUrl(path,page){{
    var n=Number(page||0);
    var url='/api/office-preview-pdf?path='+encodeURIComponent(String(path||''));
    if(n>1)url+='#page='+n;
    return url;
  }}
  async function locateOfficePage(path,snippet,fallback){{
    var fb=Number(fallback||0);
    var url='/api/office-preview-page?path='+encodeURIComponent(path)+
      '&snippet='+encodeURIComponent(snippet||'')+
      (fb>0?'&fallback='+encodeURIComponent(String(fb)):'')+
      '&convert=1';
    var response=await fetch(url,{{cache:'no-store'}});
    var data=await response.json().catch(function(){{return {{}};}});
    if(response.ok&&data&&data.ok&&Number(data.page)>0)return Number(data.page);
    return fb>0?fb:1;
  }}
  function ensureStyles(){{
    if(document.getElementById('lexiaOfficeSingleViewerStyles'))return;
    var style=document.createElement('style');
    style.id='lexiaOfficeSingleViewerStyles';
    style.textContent='\n'+
      '.lexia-office-single-backdrop{{position:fixed;inset:0;z-index:99999;background:rgba(15,23,42,.72);display:flex;align-items:center;justify-content:center;padding:22px}}\n'+
      '.lexia-office-single-modal{{width:min(1180px,96vw);height:min(860px,94vh);background:#fff;border-radius:18px;box-shadow:0 24px 80px rgba(0,0,0,.35);display:grid;grid-template-rows:auto 1fr;overflow:hidden}}\n'+
      '.lexia-office-single-head{{display:flex;align-items:center;gap:12px;padding:10px 14px;border-bottom:1px solid #e5e7eb;background:#f8fafc;font-family:system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}}\n'+
      '.lexia-office-single-title{{flex:1;min-width:0;font-weight:700;font-size:13px;color:#111827;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}\n'+
      '.lexia-office-single-page{{font-size:12px;color:#475569}}\n'+
      '.lexia-office-single-close{{border:0;background:#111827;color:#fff;border-radius:10px;padding:7px 11px;font-weight:700;cursor:pointer}}\n'+
      '.lexia-office-single-frame{{width:100%;height:100%;border:0;background:#fff}}\n'+
      '.lexia-office-single-loading{{position:fixed;z-index:99999;right:22px;bottom:22px;background:#111827;color:#fff;padding:10px 14px;border-radius:12px;font:600 13px system-ui;box-shadow:0 14px 40px rgba(0,0,0,.28)}}\n';
    document.head.appendChild(style);
  }}
  function loading(show){{
    ensureStyles();
    var id='lexiaOfficeSingleLoading';
    var old=document.getElementById(id);
    if(old)old.remove();
    if(!show)return;
    var div=document.createElement('div');
    div.id=id;
    div.className='lexia-office-single-loading';
    div.textContent='Localizando página del documento…';
    document.body.appendChild(div);
  }}
  function openOfficeModal(path,page,title){{
    ensureStyles();
    var old=document.getElementById('lexiaOfficeSingleViewer');
    if(old)old.remove();
    var backdrop=document.createElement('div');
    backdrop.id='lexiaOfficeSingleViewer';
    backdrop.className='lexia-office-single-backdrop';
    backdrop.innerHTML='<div class="lexia-office-single-modal" role="dialog" aria-modal="true">'+
      '<div class="lexia-office-single-head">'+
        '<div class="lexia-office-single-title">'+esc(title||path)+'</div>'+
        '<div class="lexia-office-single-page">Pág. '+esc(String(Number(page||1)))+'</div>'+
        '<button type="button" class="lexia-office-single-close">Cerrar</button>'+
      '</div>'+
      '<iframe class="lexia-office-single-frame" src="'+esc(officePdfUrl(path,page))+'"></iframe>'+
    '</div>';
    backdrop.querySelector('.lexia-office-single-close').addEventListener('click',function(){{backdrop.remove();}});
    backdrop.addEventListener('click',function(ev){{if(ev.target===backdrop)backdrop.remove();}});
    document.addEventListener('keydown',function escHandler(ev){{
      if(ev.key==='Escape'&&document.getElementById('lexiaOfficeSingleViewer')){{
        document.getElementById('lexiaOfficeSingleViewer').remove();
        document.removeEventListener('keydown',escHandler);
      }}
    }});
    document.body.appendChild(backdrop);
  }}

  document.addEventListener('click',async function(event){{
    var btn=event.target&&event.target.closest?event.target.closest('.search-preview-file'):null;
    if(!btn)return;
    var path=decode(btn.dataset.path||'');
    if(!isOffice(path))return;

    event.preventDefault();
    event.stopPropagation();
    if(event.stopImmediatePropagation)event.stopImmediatePropagation();

    var snippet=decode(btn.dataset.snippet||'');
    if(!snippet)snippet=String(btn.closest('.result-card')?.innerText||'').slice(0,1200);
    var page=Number(btn.dataset.page||0);
    var title=String(btn.textContent||'Documento Office').trim();
    var oldText=btn.textContent;
    try{{btn.textContent='Localizando página…';}}catch(_){{}}
    loading(true);
    try{{
      if(!(page>0))page=await locateOfficePage(path,snippet,0);
      openOfficeModal(path,page||1,title);
    }}catch(error){{
      openOfficeModal(path,1,title);
    }}finally{{
      loading(false);
      try{{btn.textContent=oldText;}}catch(_){{}}
    }}
  }},true);
}})();
</script>
'''


def backup_once(path, suffix, content):
    backup = path.with_suffix(path.suffix + suffix)
    if not backup.exists():
        backup.write_text(content, encoding="utf-8")
    return backup


def remove_script_by_id(txt, marker):
    while True:
        start = txt.find(f'<script id="{marker}">')
        if start == -1:
            return txt
        end = txt.find('</script>', start)
        if end == -1:
            return txt
        txt = txt[:start] + txt[end + len('</script>'):]


def insert_before_body(txt, script):
    if "</body>" in txt:
        return txt.replace("</body>", script + "\n</body>", 1)
    return txt + "\n" + script + "\n"


def patch_server():
    if not SERVER.exists():
        raise SystemExit(f"No existe {SERVER}")
    txt = SERVER.read_text(encoding="utf-8")
    if OFFICE_PAGE_NEW in txt:
        print("OK: server.py ya estaba en la versión correcta.")
        return
    if "office-preview-page-no-auto-convert" in txt:
        txt2 = txt.replace('"page": int(fallback) if fallback.isdigit() else 1,', '"page": int(fallback) if fallback.isdigit() else 0,')
        if txt2 == txt:
            print("OK: server.py ya tiene bloqueo Office sin devolver page=1.")
            return
    elif OFFICE_PAGE_OLD in txt:
        txt2 = txt.replace(OFFICE_PAGE_OLD, OFFICE_PAGE_NEW, 1)
    else:
        raise SystemExit("No encontré el bloque exacto de /api/office-preview-page. No modifiqué server.py.")
    backup = backup_once(SERVER, ".bak-no-auto-office", txt)
    SERVER.write_text(txt2, encoding="utf-8")
    print("OK: server.py evita LibreOffice automático y ya no devuelve page=1 sin convert=1.")
    print(f"Backup server.py: {backup}")


def patch_index():
    if not INDEX.exists():
        raise SystemExit(f"No existe {INDEX}")
    txt = INDEX.read_text(encoding="utf-8", errors="replace")
    original = txt
    changed = False

    if INDEX_NEW not in txt and INDEX_OLD in txt:
        txt = txt.replace(INDEX_OLD, INDEX_NEW, 1)
        changed = True
        print("OK: index.html conserva sourcePage cuando previewPage es 1.")

    for marker in MARKERS:
        cleaned = remove_script_by_id(txt, marker)
        if cleaned != txt:
            txt = cleaned
            changed = True
            print(f"OK: removido script anterior {marker}.")

    txt = insert_before_body(txt, SINGLE_VIEWER_SCRIPT)
    changed = True
    print("OK: DOC/RTF/DOCX/ODT usan visor único luego de calcular la página.")

    if changed:
        backup = backup_once(INDEX, ".bak-office-single-viewer", original)
        INDEX.write_text(txt, encoding="utf-8")
        print(f"Backup index.html: {backup}")


patch_server()
patch_index()
print("Listo. Reiniciá LexIA para cargar los cambios.")
