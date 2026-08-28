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
                # Devolver 0 para que el frontend conserve la página real del resultado.
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

OLD_HASH_MARKER = "LEXIA_OFFICE_PREVIEW_PAGE_HASH_FIX_20260828"
OFFICE_FORCE_MARKER = "LEXIA_OFFICE_PREVIEW_FORCE_PAGE_20260828B"
OFFICE_FORCE_SCRIPT = f'''
<script id="{OFFICE_FORCE_MARKER}">
(function(){{
  'use strict';
  if(window.__LEXIA_OFFICE_PREVIEW_FORCE_PAGE_20260828B)return;
  window.__LEXIA_OFFICE_PREVIEW_FORCE_PAGE_20260828B=true;

  function isOffice(path){{
    return /\.(doc|docx|rtf|odt)$/i.test(String(path||'').split('?')[0].split('#')[0]);
  }}

  function officePdfUrl(path,page){{
    page=Number(page||0);
    var url='/api/office-preview-pdf?path='+encodeURIComponent(String(path||''));
    if(page>1)url+='#page='+page;
    return url;
  }}

  function candidateFrames(){{
    return Array.from(document.querySelectorAll('iframe,embed,object'));
  }}

  function setFrame(el,url){{
    var tag=String(el.tagName||'').toLowerCase();
    var attr=tag==='object'?'data':'src';
    try{{el.setAttribute(attr,url);}}catch(_){{}}
  }}

  function forceOfficeFrame(path,page){{
    page=Number(page||0);
    if(!isOffice(path)||page<=1)return false;
    var url=officePdfUrl(path,page);
    var frames=candidateFrames();
    var changed=false;

    // Primero, reemplazar visores que ya estén mostrando una vista previa Office.
    frames.forEach(function(el){{
      var current=String(el.getAttribute('src')||el.getAttribute('data')||'');
      if(current.indexOf('/api/office-preview-pdf')!==-1){{
        setFrame(el,url);
        changed=true;
      }}
    }});

    // Si todavía no apareció el iframe Office, usar el iframe visible más probable del visor.
    if(!changed){{
      frames.forEach(function(el){{
        if(changed)return;
        var box;
        try{{box=el.getBoundingClientRect();}}catch(_){{box=null;}}
        if(!box||box.width<250||box.height<250)return;
        var current=String(el.getAttribute('src')||el.getAttribute('data')||'');
        if(current.indexOf('/api/file-preview')!==-1||current.indexOf('/api/office-preview')!==-1||current.indexOf('about:blank')!==-1||!current){{
          setFrame(el,url);
          changed=true;
        }}
      }});
    }}
    return changed;
  }}

  function forceRepeated(path,page){{
    var delays=[0,50,150,300,700,1200,2000];
    delays.forEach(function(ms){{setTimeout(function(){{forceOfficeFrame(path,page);}},ms);}});
    var stopAt=Date.now()+3000;
    var observer=new MutationObserver(function(){{
      forceOfficeFrame(path,page);
      if(Date.now()>stopAt)observer.disconnect();
    }});
    try{{observer.observe(document.body,{{childList:true,subtree:true,attributes:true,attributeFilter:['src','data']}});}}catch(_){{}}
    setTimeout(function(){{try{{observer.disconnect();}}catch(_){{}}}},3200);
  }}

  function install(){{
    var original=window.lexiaQuickViewerOpen;
    if(typeof original!=='function'||original.__lexiaOfficeForcePageWrapped)return false;
    var wrapped=function(path,page,snippet){{
      var n=Number(page||0);
      var office=isOffice(path);
      var result=original.apply(this,arguments);
      if(office&&n>1)forceRepeated(path,n);
      return result;
    }};
    wrapped.__lexiaOfficeForcePageWrapped=true;
    window.lexiaQuickViewerOpen=wrapped;
    return true;
  }}

  if(!install()){{
    var timer=setInterval(function(){{if(install())clearInterval(timer);}},100);
    setTimeout(function(){{clearInterval(timer);}},8000);
  }}
}})();
</script>
'''


def backup_once(path, suffix, content):
    backup = path.with_suffix(path.suffix + suffix)
    if not backup.exists():
        backup.write_text(content, encoding="utf-8")
    return backup


def remove_old_hash_script(txt):
    start = txt.find(f'<script id="{OLD_HASH_MARKER}">')
    if start == -1:
        return txt
    end = txt.find('</script>', start)
    if end == -1:
        return txt
    return txt[:start] + txt[end + len('</script>'):]


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


def patch_index_keep_source_page():
    if not INDEX.exists():
        raise SystemExit(f"No existe {INDEX}")
    txt = INDEX.read_text(encoding="utf-8", errors="replace")
    original = txt
    changed = False

    if INDEX_NEW not in txt:
        if INDEX_OLD in txt:
            txt = txt.replace(INDEX_OLD, INDEX_NEW, 1)
            changed = True
            print("OK: index.html conserva sourcePage cuando previewPage es 1.")
        else:
            print("AVISO: no encontré la línea exacta previewPage||sourcePage; no la modifiqué.")
    else:
        print("OK: index.html ya conserva sourcePage cuando previewPage es 1.")

    cleaned = remove_old_hash_script(txt)
    if cleaned != txt:
        txt = cleaned
        changed = True
        print("OK: removido fix Office anterior menos robusto.")

    if OFFICE_FORCE_MARKER not in txt:
        if "</body>" in txt:
            txt = txt.replace("</body>", OFFICE_FORCE_SCRIPT + "\n</body>", 1)
        else:
            txt = txt + "\n" + OFFICE_FORCE_SCRIPT + "\n"
        changed = True
        print("OK: index.html fuerza directamente #page=N en PDFs convertidos desde Office.")
    else:
        print("OK: index.html ya tiene fix robusto de página Office convertida.")

    if changed:
        backup = backup_once(INDEX, ".bak-office-page-force", original)
        INDEX.write_text(txt, encoding="utf-8")
        print(f"Backup index.html: {backup}")


patch_server()
patch_index_keep_source_page()
print("Listo. Reiniciá LexIA para cargar los cambios.")
