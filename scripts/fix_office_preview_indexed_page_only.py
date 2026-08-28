from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INDEX = ROOT / "app" / "ui2" / "index.html"
SERVER = ROOT / "app" / "ui2" / "server.py"

BAD_MARKERS = [
    "LEXIA_OFFICE_PREVIEW_PAGE_HASH_FIX_20260828",
    "LEXIA_OFFICE_PREVIEW_FORCE_PAGE_20260828B",
    "LEXIA_OFFICE_PREVIEW_CLICK_LOCATOR_20260828C",
    "LEXIA_OFFICE_PREVIEW_SINGLE_VIEWER_20260828D",
]

OLD_PREFETCH_FUNC = '''  async function lexiaResolveOfficeResultPage(path,snippet){
    const url=
      '/api/office-preview-page?path='+encodeURIComponent(path)+
      '&snippet='+encodeURIComponent(String(snippet||''));
    const res=await fetch(url,{cache:'no-store'});
    const data=await res.json();
    if(!res.ok||!data.ok||!Number(data.page)){
      throw new Error(data.error||`HTTP ${res.status}`);
    }
    return Number(data.page);
  }
'''

NEW_PREFETCH_FUNC = '''  async function lexiaResolveOfficeResultPage(path,snippet){
    // LEXIA_OFFICE_INDEXED_PAGE_ONLY_20260828
    // No convertir Office durante busquedas/listados.
    // La vista previa usa la pagina indexada del resultado.
    return 0;
  }
'''

# Bloque exacto del click Office visto en index.html alrededor de las lineas 4734-4753.
OLD_CLICK_BLOCK = '''      if(isOffice){
        let previewPage=parseInt(btn.dataset.previewPage||'0',10)||0;
        if(!previewPage){
          try{
            const u=
              '/api/office-preview-page?path='+encodeURIComponent(path)+
              '&snippet='+encodeURIComponent(String(snippet||''));
            const res=await fetch(u,{cache:'no-store'});
            const data=await res.json();
            if(res.ok&&data.ok&&Number(data.page)>0){
              previewPage=Number(data.page);
              btn.dataset.previewPage=String(previewPage);
            }
          }catch(_){}
        }

        if(window.lexiaQuickViewerOpen){
          window.lexiaQuickViewerOpen(path,previewPage||sourcePage,snippet);
        }
        return;
      }
'''

OLD_CLICK_BLOCK_CONVERT = '''      if(isOffice){
        let previewPage=parseInt(btn.dataset.previewPage||'0',10)||0;
        if(!previewPage){
          try{
            const u=
              '/api/office-preview-page?path='+encodeURIComponent(path)+
              '&snippet='+encodeURIComponent(String(snippet||''))+
              '&convert=1';
            const res=await fetch(u,{cache:'no-store'});
            const data=await res.json();
            if(res.ok&&data.ok&&Number(data.page)>0){
              previewPage=Number(data.page);
              btn.dataset.previewPage=String(previewPage);
            }
          }catch(_){}
        }

        if(window.lexiaQuickViewerOpen){
          window.lexiaQuickViewerOpen(path,previewPage||sourcePage,snippet);
        }
        return;
      }
'''

OLD_CLICK_BLOCK_FALLBACK = '''      if(isOffice){
        let previewPage=parseInt(btn.dataset.previewPage||'0',10)||0;
        if(!previewPage){
          try{
            const u=
              '/api/office-preview-page?path='+encodeURIComponent(path)+
              '&fallback='+encodeURIComponent(String(sourcePage||''))+
              '&snippet='+encodeURIComponent(String(snippet||''))+
              '&convert=1';
            const res=await fetch(u,{cache:'no-store'});
            const data=await res.json();
            if(res.ok&&data.ok&&Number(data.page)>0){
              previewPage=Number(data.page);
              btn.dataset.previewPage=String(previewPage);
            }
          }catch(_){}
        }

        if(window.lexiaQuickViewerOpen){
          window.lexiaQuickViewerOpen(path,((previewPage&&previewPage>1)?previewPage:sourcePage)||1,snippet);
        }
        return;
      }
'''

NEW_CLICK_BLOCK = '''      if(isOffice){
        // LEXIA_OFFICE_INDEXED_PAGE_ONLY_20260828
        // No llamar a /api/office-preview-page en el click: ese calculo devuelve 1
        // en muchos .doc y pisa la pagina real del resultado.
        if(btn.dataset.previewPage==='1'){
          delete btn.dataset.previewPage;
        }

        let indexedPage=parseInt(btn.dataset.page||'0',10)||0;
        if(!indexedPage){
          const metaText=String(card?.querySelector?.('.result-meta')?.textContent||'');
          const m=metaText.match(/p[áa]g\.\s*(\d+)/i);
          if(m) indexedPage=parseInt(m[1],10)||0;
        }

        const pageToOpen=(indexedPage&&indexedPage>0)?indexedPage:1;
        if(window.lexiaQuickViewerOpen){
          window.lexiaQuickViewerOpen(path,pageToOpen,snippet);
        }
        return;
      }
'''

SERVER_BAD = '''        if path == "/api/office-preview-page":
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

SERVER_GOOD = '''        if path == "/api/office-preview-page":
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


def backup_once(path: Path, suffix: str, text: str) -> Path:
    backup = path.with_suffix(path.suffix + suffix)
    if not backup.exists():
        backup.write_text(text, encoding="utf-8")
    return backup


def remove_script_by_id(text: str, marker: str) -> str:
    while True:
        start = text.find(f'<script id="{marker}">')
        if start < 0:
            return text
        end = text.find('</script>', start)
        if end < 0:
            return text
        text = text[:start] + text[end + len('</script>'):]


def patch_server() -> bool:
    if not SERVER.exists():
        raise SystemExit(f"No existe {SERVER}")
    text = SERVER.read_text(encoding="utf-8")
    new = text.replace(SERVER_BAD, SERVER_GOOD, 1)
    if new == text:
        print("OK: server.py sin cambios necesarios.")
        return False
    backup = backup_once(SERVER, ".bak-office-indexed-page-only", text)
    SERVER.write_text(new, encoding="utf-8")
    print("OK: server.py restaurado para vista previa Office original.")
    print(f"Backup server.py: {backup}")
    return True


def patch_index() -> bool:
    if not INDEX.exists():
        raise SystemExit(f"No existe {INDEX}")
    text = INDEX.read_text(encoding="utf-8", errors="replace")
    original = text

    for marker in BAD_MARKERS:
        text = remove_script_by_id(text, marker)

    if "LEXIA_OFFICE_INDEXED_PAGE_ONLY_20260828" not in text:
        if OLD_PREFETCH_FUNC in text:
            text = text.replace(OLD_PREFETCH_FUNC, NEW_PREFETCH_FUNC, 1)
        elif "LEXIA_OFFICE_NO_PREFETCH_20260828" in text:
            text = text.replace("LEXIA_OFFICE_NO_PREFETCH_20260828", "LEXIA_OFFICE_INDEXED_PAGE_ONLY_20260828")
        else:
            print("AVISO: no encontré la función de precálculo Office original; continúo con click.")

    replaced = False
    for old in (OLD_CLICK_BLOCK_FALLBACK, OLD_CLICK_BLOCK_CONVERT, OLD_CLICK_BLOCK):
        if old in text:
            text = text.replace(old, NEW_CLICK_BLOCK, 1)
            replaced = True
            break
    if not replaced and "LEXIA_OFFICE_INDEXED_PAGE_ONLY_20260828" not in text[text.find("if(isOffice){") if "if(isOffice){" in text else 0:]:
        raise SystemExit("No encontré el bloque exacto del click Office. No modifiqué index.html.")

    if text == original:
        print("OK: index.html ya estaba ajustado para usar pagina indexada en Office.")
        return False

    backup = backup_once(INDEX, ".bak-office-indexed-page-only", original)
    INDEX.write_text(text, encoding="utf-8")
    print("OK: index.html usa page_start/pág. visible para Office y no calcula página al click.")
    print(f"Backup index.html: {backup}")
    return True


def main() -> None:
    patch_server()
    patch_index()
    print("Listo. Reiniciá LexIA y recargá con Cmd+Shift+R.")


if __name__ == "__main__":
    main()
