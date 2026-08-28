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
            raise SystemExit("server.py ya tiene bloqueo Office, pero no encontré la línea page fallback para corregir.")
    elif OFFICE_PAGE_OLD in txt:
        txt2 = txt.replace(OFFICE_PAGE_OLD, OFFICE_PAGE_NEW, 1)
    else:
        raise SystemExit("No encontré el bloque exacto de /api/office-preview-page. No modifiqué server.py.")
    backup = SERVER.with_suffix(SERVER.suffix + ".bak-no-auto-office")
    if not backup.exists():
        backup.write_text(txt, encoding="utf-8")
    SERVER.write_text(txt2, encoding="utf-8")
    print("OK: server.py evita LibreOffice automático y ya no devuelve page=1 sin convert=1.")


def patch_index():
    if not INDEX.exists():
        raise SystemExit(f"No existe {INDEX}")
    txt = INDEX.read_text(encoding="utf-8", errors="replace")
    if INDEX_NEW in txt:
        print("OK: index.html ya conserva sourcePage cuando previewPage es 1.")
        return
    if INDEX_OLD not in txt:
        raise SystemExit("No encontré la línea exacta del visor profesional. No modifiqué index.html.")
    backup = INDEX.with_suffix(INDEX.suffix + ".bak-office-page")
    if not backup.exists():
        backup.write_text(txt, encoding="utf-8")
    INDEX.write_text(txt.replace(INDEX_OLD, INDEX_NEW, 1), encoding="utf-8")
    print("OK: index.html ya no deja que page=1 pise la página del resultado.")


patch_server()
patch_index()
print("Listo. Reiniciá LexIA para cargar los cambios.")
