from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SERVER = ROOT / "app" / "ui2" / "server.py"
INDEX = ROOT / "app" / "ui2" / "index.html"

OLD_SERVER_BLOCK = '''        if path == "/api/office-preview-page":
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

NEW_SERVER_BLOCK = '''        if path == "/api/office-preview-page":
            try:
                query = parse_qs(urlparse(self.path).query)
                requested = str((query.get("path") or [""])[0] or "").strip()
                snippet = str((query.get("snippet") or [""])[0] or "")
                fallback = str((query.get("fallback") or [""])[0] or "").strip()
                convert = str((query.get("convert") or [""])[0] or "").strip().lower()

                if not requested:
                    return self._json({"ok": False, "error": "Falta path"}, 400)

                # Seguridad: no convertir Office en llamadas automáticas de búsqueda/listado.
                # Sólo una vista previa explícita debe llamar con convert=1.
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

OLD_MARKERS = [
    "LEXIA_OFFICE_PREVIEW_PAGE_HASH_FIX_20260828",
    "LEXIA_OFFICE_PREVIEW_FORCE_PAGE_20260828B",
    "LEXIA_OFFICE_PREVIEW_CLICK_LOCATOR_20260828C",
    "LEXIA_OFFICE_PREVIEW_SINGLE_VIEWER_20260828D",
]


def backup_once(path: Path, suffix: str, content: str) -> Path:
    backup = path.with_suffix(path.suffix + suffix)
    if not backup.exists():
        backup.write_text(content, encoding="utf-8")
    return backup


def remove_script_by_id(txt: str, marker: str) -> str:
    start = txt.find(f'<script id="{marker}">')
    if start == -1:
        return txt
    end = txt.find('</script>', start)
    if end == -1:
        return txt
    return txt[:start] + txt[end + len('</script>'):]


def patch_server() -> None:
    if not SERVER.exists():
        raise SystemExit(f"No existe {SERVER}")
    txt = SERVER.read_text(encoding="utf-8")

    if "office-preview-page-no-auto-convert" in txt:
        print("OK: server.py ya bloquea conversión automática en office-preview-page.")
        return

    if OLD_SERVER_BLOCK not in txt:
        raise SystemExit("No encontré el bloque original de /api/office-preview-page. No modifiqué server.py.")

    backup = backup_once(SERVER, ".bak-office-no-search-convert", txt)
    SERVER.write_text(txt.replace(OLD_SERVER_BLOCK, NEW_SERVER_BLOCK, 1), encoding="utf-8")
    print("OK: server.py parcheado: /api/office-preview-page sólo convierte con convert=1.")
    print(f"Backup server.py: {backup}")


def patch_index() -> None:
    if not INDEX.exists():
        raise SystemExit(f"No existe {INDEX}")
    txt = INDEX.read_text(encoding="utf-8", errors="replace")
    original = txt
    changed = False

    # Remover únicamente scripts inyectados por parches anteriores, si existieran.
    for marker in OLD_MARKERS:
        cleaned = remove_script_by_id(txt, marker)
        if cleaned != txt:
            txt = cleaned
            changed = True
            print(f"OK: removido script inyectado anterior: {marker}")

    # Agregar convert=1 sólo dentro de showViewer, que es vista previa explícita.
    start = txt.find("function showViewer")
    end = txt.find("window.lexiaQuickViewerOpen=showViewer", start)
    if start == -1 or end == -1:
        raise SystemExit("No pude delimitar showViewer en index.html. No modifiqué index.html.")

    segment = txt[start:end]
    needle = "'/api/office-preview-page?path='+encodeURIComponent(path)+"
    replacement = "'/api/office-preview-page?path='+encodeURIComponent(path)+'&convert=1'+"

    if replacement in segment:
        print("OK: showViewer ya usa convert=1 para localizar página Office.")
    elif needle in segment:
        segment2 = segment.replace(needle, replacement, 1)
        txt = txt[:start] + segment2 + txt[end:]
        changed = True
        print("OK: index.html parcheado: sólo showViewer llama office-preview-page con convert=1.")
    else:
        raise SystemExit("No encontré la llamada office-preview-page dentro de showViewer. No modifiqué index.html.")

    if changed:
        backup = backup_once(INDEX, ".bak-office-no-search-convert", original)
        INDEX.write_text(txt, encoding="utf-8")
        print(f"Backup index.html: {backup}")
    else:
        print("OK: index.html no necesitaba cambios adicionales.")


def report_calls() -> None:
    txt = INDEX.read_text(encoding="utf-8", errors="replace")
    print("\nLlamadas office-preview-page encontradas:")
    for n, line in enumerate(txt.splitlines(), 1):
        if "office-preview-page" in line:
            print(f"{n}: {line.strip()[:220]}")


patch_server()
patch_index()
report_calls()
print("\nListo. Reiniciá LexIA para cargar server.py e index.html actualizados.")
