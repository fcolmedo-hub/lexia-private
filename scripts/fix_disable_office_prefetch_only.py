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
    // La vista previa real conserva su flujo propio: al hacer click usa
    // /api/office-preview-page y /api/office-preview-pdf para convertir y localizar.
    return 0;
  }
'''

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


def patch_index_disable_prefetch() -> bool:
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

    if text == original:
        print("OK: index.html ya tenía desactivado el precálculo Office de búsqueda.")
        return False

    backup = backup_once(INDEX, ".bak-office-prefetch-only", original)
    INDEX.write_text(text, encoding="utf-8")
    print("OK: index.html ahora no convierte Office durante búsquedas/listados.")
    print(f"Backup index.html: {backup}")
    return True


def main() -> None:
    patch_server_back_to_preview_behavior()
    patch_index_disable_prefetch()
    print("Listo. Reiniciá LexIA. Prueba: buscar no debe abrir LibreOffice; vista previa DOC debe seguir funcionando.")


if __name__ == "__main__":
    main()
