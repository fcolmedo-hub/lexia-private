from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INDEX = ROOT / "app" / "ui2" / "index.html"
SERVER = ROOT / "app" / "ui2" / "server.py"

OLD_FUNC = '''  async function lexiaResolveOfficeResultPage(path,snippet){
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

NEW_FUNC = '''  async function lexiaResolveOfficeResultPage(path,snippet){
    // LEXIA_OFFICE_NO_PREFETCH_20260828
    // No convertir documentos Office durante busquedas/listados.
    // La pagina se calcula solamente al abrir la vista previa real.
    return 0;
  }
'''

VIEWER_META_OLD = '''          const metaUrl=
            '/api/office-preview-page?path='+encodeURIComponent(path)+
            '&fallback='+encodeURIComponent(requestedPage)+
            '&snippet='+encodeURIComponent(String(snippet||''));
'''

VIEWER_META_NEW = '''          const metaUrl=
            '/api/office-preview-page?path='+encodeURIComponent(path)+
            '&fallback='+encodeURIComponent(requestedPage)+
            '&snippet='+encodeURIComponent(String(snippet||''))+
            '&convert=1';
'''

CLICK_META_OLD = '''            const u=
              '/api/office-preview-page?path='+encodeURIComponent(path)+
              '&snippet='+encodeURIComponent(String(snippet||''));
'''

CLICK_META_CONVERT_ONLY = '''            const u=
              '/api/office-preview-page?path='+encodeURIComponent(path)+
              '&snippet='+encodeURIComponent(String(snippet||''))+
              '&convert=1';
'''

CLICK_META_NEW = '''            const u=
              '/api/office-preview-page?path='+encodeURIComponent(path)+
              '&fallback='+encodeURIComponent(String(sourcePage||''))+
              '&snippet='+encodeURIComponent(String(snippet||''))+
              '&convert=1';
'''

OPEN_OLD = "window.lexiaQuickViewerOpen(path,previewPage||sourcePage,snippet);"
OPEN_NEW = "window.lexiaQuickViewerOpen(path,((previewPage&&previewPage>1)?previewPage:sourcePage)||1,snippet);"

BAD_MARKERS = [
    "LEXIA_OFFICE_PREVIEW_PAGE_HASH_FIX_20260828",
    "LEXIA_OFFICE_PREVIEW_FORCE_PAGE_20260828B",
    "LEXIA_OFFICE_PREVIEW_CLICK_LOCATOR_20260828C",
    "LEXIA_OFFICE_PREVIEW_SINGLE_VIEWER_20260828D",
]

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


def patch_server_back_to_preview_behavior() -> bool:
    if not SERVER.exists():
        raise SystemExit(f"No existe {SERVER}")
    text = SERVER.read_text(encoding="utf-8")
    new = text.replace(SERVER_BAD, SERVER_GOOD, 1)
    if new == text:
        print("OK: server.py queda sin bloqueo global; vista previa Office conserva el flujo original.")
        return False
    backup = backup_once(SERVER, ".bak-office-prefetch-only", text)
    SERVER.write_text(new, encoding="utf-8")
    print("OK: server.py restaurado para no romper vista previa Office.")
    print(f"Backup server.py: {backup}")
    return True


def patch_index_disable_prefetch_and_preserve_result_page() -> bool:
    if not INDEX.exists():
        raise SystemExit(f"No existe {INDEX}")
    text = INDEX.read_text(encoding="utf-8", errors="replace")
    original = text

    for marker in BAD_MARKERS:
        text = remove_script_by_id(text, marker)

    if "LEXIA_OFFICE_NO_PREFETCH_20260828" not in text:
        if OLD_FUNC not in text:
            raise SystemExit("No encontré la función exacta lexiaResolveOfficeResultPage. No modifiqué index.html.")
        text = text.replace(OLD_FUNC, NEW_FUNC, 1)

    if VIEWER_META_OLD in text:
        text = text.replace(VIEWER_META_OLD, VIEWER_META_NEW, 1)

    if CLICK_META_OLD in text:
        text = text.replace(CLICK_META_OLD, CLICK_META_NEW, 1)
    elif CLICK_META_CONVERT_ONLY in text:
        text = text.replace(CLICK_META_CONVERT_ONLY, CLICK_META_NEW, 1)
    elif CLICK_META_NEW in text:
        pass
    else:
        print("AVISO: no encontré el metaUrl del click Office; no lo modifiqué.")

    if OPEN_OLD in text:
        text = text.replace(OPEN_OLD, OPEN_NEW, 1)
    elif OPEN_NEW in text:
        pass
    else:
        print("AVISO: no encontré la llamada window.lexiaQuickViewerOpen del click Office.")

    if text == original:
        print("OK: index.html ya tenía el ajuste de Office aplicado.")
        return False

    backup = backup_once(INDEX, ".bak-office-prefetch-only", original)
    INDEX.write_text(text, encoding="utf-8")
    print("OK: index.html no convierte Office durante búsquedas y no pisa sourcePage con page=1.")
    print(f"Backup index.html: {backup}")
    return True


def main() -> None:
    patch_server_back_to_preview_behavior()
    patch_index_disable_prefetch_and_preserve_result_page()
    print("Listo. Reiniciá LexIA. Prueba: buscar no debe abrir LibreOffice; vista previa DOC debe usar page_start si el cálculo devuelve 1.")


if __name__ == "__main__":
    main()
