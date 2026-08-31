from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
UI2 = ROOT / "app" / "ui2"
SERVER = UI2 / "server.py"
INDEX = UI2 / "index.html"
NAVIGATORS = sorted(UI2.glob("navigator_*.js"))

SERVER_OLD = 'if source.suffix.lower() not in {".doc", ".docx", ".rtf", ".odt"}:'
SERVER_NEW = 'if source.suffix.lower() not in {".doc", ".docx", ".rtf", ".odt", ".html", ".htm"}:'

ARRAY_OLD = "['.doc','.docx','.rtf','.odt']"
ARRAY_NEW = "['.doc','.docx','.rtf','.odt','.html','.htm']"

REGEX_REPLACEMENTS = (
    (r'/\.(doc|docx|rtf|odt)$/i', r'/\.(doc|docx|rtf|odt|html|htm)$/i'),
    (r'/\.(doc|docx|rtf|odt)(?:\?|#|$)/i', r'/\.(doc|docx|rtf|odt|html|htm)(?:\?|#|$)/i'),
)

MARKER = "LEXIA_HTML_PREVIEW_20260831"


def backup_once(path: Path, original: str) -> Path:
    backup = path.with_suffix(path.suffix + ".bak-html-preview")
    if not backup.exists():
        backup.write_text(original, encoding="utf-8")
    return backup


def write_if_changed(path: Path, original: str, updated: str) -> bool:
    if updated == original:
        return False
    backup = backup_once(path, original)
    path.write_text(updated, encoding="utf-8")
    print(f"OK: {path.relative_to(ROOT)}")
    print(f"    backup: {backup.relative_to(ROOT)}")
    return True


def patch_server() -> bool:
    text = SERVER.read_text(encoding="utf-8")
    if SERVER_NEW in text:
        print("OK: server.py ya admite HTML/HTM en el conversor de vista previa.")
        return False
    if SERVER_OLD not in text:
        raise SystemExit(
            "No encontré la lista exacta de extensiones de _office_preview_pdf; "
            "no modifiqué server.py."
        )
    updated = text.replace(SERVER_OLD, SERVER_NEW, 1)
    return write_if_changed(SERVER, text, updated)


def patch_index() -> bool:
    text = INDEX.read_text(encoding="utf-8", errors="replace")
    original = text

    # El visor principal decide por extensión si usa el PDF temporal de LibreOffice
    # o si muestra el archivo como texto. HTML/HTM deben entrar al mismo circuito
    # explícito de DOC/DOCX/RTF/ODT para no exhibir las etiquetas del documento.
    replacements = 0
    for old, new in REGEX_REPLACEMENTS:
        count = text.count(old)
        if count:
            text = text.replace(old, new)
            replacements += count

    array_count = text.count(ARRAY_OLD)
    if array_count:
        text = text.replace(ARRAY_OLD, ARRAY_NEW)
        replacements += array_count

    if MARKER not in text and replacements:
        marker_script = (
            f'\n<script id="{MARKER}">\n'
            "// HTML/HTM se visualizan mediante el mismo PDF temporal que Office.\n"
            "</script>\n"
        )
        if "</body>" in text:
            text = text.replace("</body>", marker_script + "</body>", 1)

    if text == original:
        if "html|htm" in text or ARRAY_NEW in text:
            print("OK: index.html ya reconoce HTML/HTM como vista convertible.")
            return False
        raise SystemExit(
            "No encontré en index.html los detectores conocidos del visor Office. "
            "No modifiqué el archivo."
        )

    changed = write_if_changed(INDEX, original, text)
    print(f"    detectores actualizados: {replacements}")
    return changed


def patch_navigators() -> int:
    changed = 0
    found = 0
    for path in NAVIGATORS:
        text = path.read_text(encoding="utf-8", errors="replace")
        if ARRAY_NEW in text:
            found += 1
            print(f"OK: {path.name} ya admite HTML/HTM.")
            continue
        if ARRAY_OLD not in text:
            continue
        found += 1
        updated = text.replace(ARRAY_OLD, ARRAY_NEW)
        if write_if_changed(path, text, updated):
            changed += 1

    if not found:
        raise SystemExit(
            "No encontré el detector de extensiones de vista rápida en los navegadores."
        )
    return changed


def verify() -> None:
    server = SERVER.read_text(encoding="utf-8")
    index = INDEX.read_text(encoding="utf-8", errors="replace")

    if SERVER_NEW not in server:
        raise SystemExit("VERIFICACIÓN FALLÓ: server.py no admite .html/.htm.")

    if not ("html|htm" in index or ARRAY_NEW in index):
        raise SystemExit("VERIFICACIÓN FALLÓ: el visor principal no reconoce HTML/HTM.")

    navigator_ok = False
    for path in NAVIGATORS:
        text = path.read_text(encoding="utf-8", errors="replace")
        if ARRAY_NEW in text:
            navigator_ok = True
            break
    if not navigator_ok:
        raise SystemExit("VERIFICACIÓN FALLÓ: ningún navegador reconoce HTML/HTM.")

    print("\nVERIFICACIÓN OK")
    print("- Los originales .htm/.html no se modifican.")
    print("- El visor los convierte a PDF temporal mediante LibreOffice al abrirlos.")
    print("- La conversión sigue usando preview_cache y no ocurre durante la búsqueda.")


def main() -> None:
    if not SERVER.exists() or not INDEX.exists():
        raise SystemExit("No parece ser una instalación válida de LexIA UI2.")

    print("=== LexIA · soporte de vista previa HTML/HTM ===")
    patch_server()
    patch_index()
    patch_navigators()
    verify()
    print("\nListo. Reiniciá LexIA para cargar los cambios.")


if __name__ == "__main__":
    main()
