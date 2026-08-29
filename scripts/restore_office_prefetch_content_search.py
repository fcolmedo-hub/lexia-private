from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INDEX = ROOT / "app" / "ui2" / "index.html"
SERVER = ROOT / "app" / "ui2" / "server.py"

DISABLED_FUNC = '''  async function lexiaResolveOfficeResultPage(path,snippet){
    // LEXIA_OFFICE_NO_PREFETCH_20260828
    // No convertir documentos Office durante busquedas/listados.
    // La pagina se calcula solamente al abrir la vista previa real.
    return 0;
  }
'''

RESTORED_FUNC = '''  async function lexiaResolveOfficeResultPage(path,snippet){
    // LEXIA_OFFICE_PREFETCH_RESTORED_20260829
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

SERVER_GATED = '''        if path == "/api/office-preview-page":
            try:
                query = parse_qs(urlparse(self.path).query)
                requested = str((query.get("path") or [""])[0] or "").strip()
                snippet = str((query.get("snippet") or [""])[0] or "")
                fallback = str((query.get("fallback") or [""])[0] or "").strip()
                convert = str((query.get("convert") or [""])[0] or "").strip().lower()

                if not requested:
                    return self._json({"ok": False, "error": "Falta path"}, 400)

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

SERVER_UNGATED = '''        if path == "/api/office-preview-page":
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


def backup_once(path: Path, suffix: str, original: str) -> Path:
    backup = path.with_suffix(path.suffix + suffix)
    if not backup.exists():
        backup.write_text(original, encoding="utf-8")
    return backup


def patch_index() -> None:
    text = INDEX.read_text(encoding="utf-8", errors="replace")
    original = text

    if DISABLED_FUNC in text:
        text = text.replace(DISABLED_FUNC, RESTORED_FUNC, 1)
    elif "LEXIA_OFFICE_PREFETCH_RESTORED_20260829" in text:
        pass
    elif "async function lexiaResolveOfficeResultPage(path,snippet){" in text and "/api/office-preview-page?path=" in text:
        print("OK: lexiaResolveOfficeResultPage ya realiza la consulta de prefetch.")
    else:
        raise SystemExit(
            "No encontré el bloque esperado lexiaResolveOfficeResultPage; no modifiqué index.html."
        )

    # El prefetch debe quedar limitado a búsqueda profesional/contenido.
    required = "if(which!=='professional'||!box)return;"
    if required not in text:
        raise SystemExit(
            "No encontré la protección de modo professional en lexiaHydrateOfficeResultPages; no modifiqué index.html."
        )

    if text != original:
        backup = backup_once(INDEX, ".bak-restore-office-prefetch-20260829", original)
        INDEX.write_text(text, encoding="utf-8")
        print("OK: restaurado prefetch Office en búsqueda por contenido.")
        print(f"Backup index.html: {backup}")
    else:
        print("OK: index.html ya tenía el prefetch Office activo.")


def patch_server() -> None:
    text = SERVER.read_text(encoding="utf-8", errors="replace")
    original = text

    if SERVER_GATED in text:
        text = text.replace(SERVER_GATED, SERVER_UNGATED, 1)
        backup = backup_once(SERVER, ".bak-restore-office-prefetch-20260829", original)
        SERVER.write_text(text, encoding="utf-8")
        print("OK: /api/office-preview-page vuelve a convertir también durante prefetch.")
        print(f"Backup server.py: {backup}")
    else:
        print("OK: server.py no tiene bloqueo de conversión automática Office.")


def main() -> None:
    if not INDEX.exists() or not SERVER.exists():
        raise SystemExit("No encontré app/ui2/index.html o app/ui2/server.py")

    patch_server()
    patch_index()

    print("LISTO")
    print("- Búsqueda por contenido/professional: DOC/DOCX/RTF/ODT se precalculan con LibreOffice.")
    print("- La página del PDF temporal se localiza usando el fragmento encontrado.")
    print("- El buscador por nombre no activa este prefetch.")
    print("- Al hacer click, si el prefetch ya terminó, la vista previa abre en la página preparada.")


if __name__ == "__main__":
    main()
