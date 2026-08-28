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

OFFICE_HASH_MARKER = "LEXIA_OFFICE_PREVIEW_PAGE_HASH_FIX_20260828"
OFFICE_HASH_SCRIPT = f'''
<script id="{OFFICE_HASH_MARKER}">
(function(){{
  'use strict';
  if(window.__LEXIA_OFFICE_PREVIEW_PAGE_HASH_FIX_20260828)return;
  window.__LEXIA_OFFICE_PREVIEW_PAGE_HASH_FIX_20260828=true;

  function isOffice(path){{
    return /\.(doc|docx|rtf|odt)$/i.test(String(path||'').split('?')[0]);
  }}

  function forceOfficePreviewPage(path,page){{
    page=Number(page||0);
    if(!isOffice(path)||page<=1)return;
    const encoded=encodeURIComponent(String(path||''));
    const wanted='#page='+page;
    const selectors=[
      'iframe[src*="/api/office-preview-pdf"]',
      'embed[src*="/api/office-preview-pdf"]',
      'object[data*="/api/office-preview-pdf"]'
    ];
    document.querySelectorAll(selectors.join(',')).forEach(el=>{{
      const attr=el.tagName.toLowerCase()==='object'?'data':'src';
      const current=String(el.getAttribute(attr)||'');
      if(!current||!current.includes('/api/office-preview-pdf'))return;
      if(encoded&& !current.includes(encoded))return;
      const clean=current.replace(/#page=\d+$/,'');
      const next=clean+wanted;
      if(current!==next)el.setAttribute(attr,next);
    }});
  }}

  function install(){{
    const original=window.lexiaQuickViewerOpen;
    if(typeof original!=='function'||original.__lexiaOfficePageHashWrapped)return false;
    const wrapped=function(path,page,snippet){{
      const result=original.apply(this,arguments);
      if(isOffice(path)&&Number(page||0)>1){{
        setTimeout(()=>forceOfficePreviewPage(path,page),50);
        setTimeout(()=>forceOfficePreviewPage(path,page),250);
        setTimeout(()=>forceOfficePreviewPage(path,page),800);
      }}
      return result;
    }};
    wrapped.__lexiaOfficePageHashWrapped=true;
    window.lexiaQuickViewerOpen=wrapped;
    return true;
  }}

  if(!install()){{
    const timer=setInterval(()=>{{if(install())clearInterval(timer);}},100);
    setTimeout(()=>clearInterval(timer),5000);
  }}
}})();
</script>
'''


def backup_once(path, suffix, content):
    backup = path.with_suffix(path.suffix + suffix)
    if not backup.exists():
        backup.write_text(content, encoding="utf-8")
    return backup


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
    changed = False
    if INDEX_NEW not in txt:
        if INDEX_OLD in txt:
            backup_once(INDEX, ".bak-office-page", txt)
            txt = txt.replace(INDEX_OLD, INDEX_NEW, 1)
            changed = True
            print("OK: index.html conserva sourcePage cuando previewPage es 1.")
        else:
            print("AVISO: no encontré la línea exacta previewPage||sourcePage; no la modifiqué.")
    else:
        print("OK: index.html ya conserva sourcePage cuando previewPage es 1.")

    if OFFICE_HASH_MARKER not in txt:
        backup_once(INDEX, ".bak-office-page-hash", txt)
        if "</body>" in txt:
            txt = txt.replace("</body>", OFFICE_HASH_SCRIPT + "\n</body>", 1)
        else:
            txt = txt + "\n" + OFFICE_HASH_SCRIPT + "\n"
        changed = True
        print("OK: index.html fuerza #page=N en PDFs convertidos desde DOC/RTF/DOCX/ODT.")
    else:
        print("OK: index.html ya tiene fix de página Office convertida.")

    if changed:
        INDEX.write_text(txt, encoding="utf-8")


patch_server()
patch_index_keep_source_page()
print("Listo. Reiniciá LexIA para cargar los cambios.")