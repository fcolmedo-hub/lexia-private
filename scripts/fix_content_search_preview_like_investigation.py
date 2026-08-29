from __future__ import annotations

from pathlib import Path
import shutil
import sys

ROOT = Path.cwd()
TARGET = ROOT / "app" / "ui2" / "index.html"
BACKUP = ROOT / "app" / "ui2" / "index.html.bak-content-search-preview-like-investigation"

if not TARGET.exists():
    raise SystemExit(f"ERROR: no existe {TARGET}")

text = TARGET.read_text(encoding="utf-8")
original = text

# Idempotencia: si las tres marcas ya estan presentes, no volver a modificar.
MARK_HYDRATE = "LEXIA_SEARCH_OFFICE_NO_PREFETCH"
MARK_CLICK = "LEXIA_SEARCH_OFFICE_TEXT_PREVIEW"
MARK_CAPTURE = "LEXIA_SEARCH_OFFICE_SKIP_PAGE_CAPTURE"
if all(mark in text for mark in (MARK_HYDRATE, MARK_CLICK, MARK_CAPTURE)):
    print("OK: el Buscador de contenido ya usa la vista previa Office de Investigacion.")
    raise SystemExit(0)

# 1) No convertir/precalcular paginas Office al mostrar resultados.
hydrate_old = """  function lexiaHydrateOfficeResultPages(box,which){\n    if(which!=='professional'||!box)return;"""
hydrate_new = """  function lexiaHydrateOfficeResultPages(box,which){\n    // LEXIA_SEARCH_OFFICE_NO_PREFETCH: Investigacion no precalcula paginas Office.\n    return;\n    if(which!=='professional'||!box)return;"""
if MARK_HYDRATE not in text:
    count = text.count(hydrate_old)
    if count < 1:
        raise SystemExit("ERROR: no se encontro lexiaHydrateOfficeResultPages; no se modifico el archivo.")
    text = text.replace(hydrate_old, hydrate_new)
    print(f"OK: desactivado prefetch Office ({count} bloque/s).")

# 2) El handler capturador de paginas no debe interceptar DOC/DOCX/RTF/ODT.
capture_old = """    const btn=ev.target.closest?.('.search-preview-file[data-page]');\n    if(!btn)return;\n    const sourcePage=parseInt(btn.dataset.page||'0',10);"""
capture_new = """    const btn=ev.target.closest?.('.search-preview-file[data-page]');\n    if(!btn)return;\n    // LEXIA_SEARCH_OFFICE_SKIP_PAGE_CAPTURE: dejar Office al mismo visor de Investigacion.\n    const officePath=decodeURIComponent(btn.dataset.path||'');\n    const officeExt=(officePath.toLowerCase().match(/(\\.[^.\\\\/]+)$/)||[])[1]||'';\n    if(['.doc','.docx','.rtf','.odt'].includes(officeExt))return;\n    const sourcePage=parseInt(btn.dataset.page||'0',10);"""
if MARK_CAPTURE not in text:
    count = text.count(capture_old)
    if count < 1:
        raise SystemExit("ERROR: no se encontro FINAL PAGE PREVIEW; no se modifico el archivo.")
    text = text.replace(capture_old, capture_new)
    print(f"OK: Office excluido del capturador de paginas ({count} bloque/s).")

# 3) Al hacer clic en un resultado Office, abrir ruta + snippet SIN pagina.
#    Esto fuerza la vista de texto extraido del visor comun, que marca el snippet
#    con <mark> (amarillo) y hace scroll hasta la coincidencia, igual que Investigacion.
click_old = """          const effectivePath=path||requestedPath;\n\n          if(\n            resultSnippet &&\n            lexiaIsOfficeResult(effectivePath) &&"""
click_new = """          const effectivePath=path||requestedPath;\n\n          // LEXIA_SEARCH_OFFICE_TEXT_PREVIEW: copiar el comportamiento de Investigacion.\n          if(lexiaIsOfficeResult(effectivePath)){\n            if(window.lexiaQuickViewerOpen){\n              window.lexiaQuickViewerOpen(effectivePath,undefined,resultSnippet);\n            }\n            return;\n          }\n\n          if(\n            resultSnippet &&\n            lexiaIsOfficeResult(effectivePath) &&"""
if MARK_CLICK not in text:
    count = text.count(click_old)
    if count < 1:
        raise SystemExit("ERROR: no se encontro el click del Buscador de contenido; no se modifico el archivo.")
    text = text.replace(click_old, click_new)
    print(f"OK: click Office conectado a texto+snippet ({count} bloque/s).")

# Verificacion final antes de escribir.
missing = [mark for mark in (MARK_HYDRATE, MARK_CLICK, MARK_CAPTURE) if mark not in text]
if missing:
    raise SystemExit("ERROR: verificacion incompleta; no se modifico el archivo: " + ", ".join(missing))

if text == original:
    print("OK: no habia cambios pendientes.")
    raise SystemExit(0)

if not BACKUP.exists():
    shutil.copy2(TARGET, BACKUP)
    print(f"Backup: {BACKUP}")
else:
    print(f"Backup existente conservado: {BACKUP}")

TARGET.write_text(text, encoding="utf-8", newline="")
print("OK: Buscador de contenido reparado.")
print("DOC/DOCX/RTF/ODT ahora abren como texto extraido + snippet resaltado en amarillo, igual que Investigacion.")
print("Investigacion no fue modificada.")
