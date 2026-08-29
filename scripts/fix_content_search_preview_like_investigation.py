from __future__ import annotations

from pathlib import Path
import shutil

ROOT = Path.cwd()
TARGET = ROOT / "app" / "ui2" / "index.html"
BACKUP = ROOT / "app" / "ui2" / "index.html.bak-before-restore-office-page-preview"

if not TARGET.exists():
    raise SystemExit(f"ERROR: no existe {TARGET}")

raw = TARGET.read_bytes()
has_bom = raw.startswith(b"\xef\xbb\xbf")
payload = raw[3:] if has_bom else raw
text = payload.decode("utf-8")
original = text
EOL = "\r\n" if "\r\n" in text else "\n"

def nl(value: str) -> str:
    return value.replace("\n", EOL)

MARK_HYDRATE = "LEXIA_SEARCH_OFFICE_NO_PREFETCH"
MARK_CLICK = "LEXIA_SEARCH_OFFICE_TEXT_PREVIEW"
MARK_CAPTURE = "LEXIA_SEARCH_OFFICE_SKIP_PAGE_CAPTURE"

# OPCION A — comportamiento original del Buscador de contenido para Office:
# LibreOffice trabaja durante la busqueda, se resuelve la pagina correcta y
# el click abre inmediatamente esa pagina.

# 1) Reactivar el prefetch/resolucion de pagina Office durante la busqueda.
hydrate_modified = nl("""  function lexiaHydrateOfficeResultPages(box,which){
    // LEXIA_SEARCH_OFFICE_NO_PREFETCH: Investigacion no precalcula paginas Office.
    return;
    if(which!=='professional'||!box)return;""")
hydrate_original = nl("""  function lexiaHydrateOfficeResultPages(box,which){
    if(which!=='professional'||!box)return;""")

if hydrate_modified in text:
    text = text.replace(hydrate_modified, hydrate_original)
    print("OK: reactivado LibreOffice durante la busqueda para resultados Office.")
elif hydrate_original in text:
    print("OK: el prefetch Office ya estaba activo.")
else:
    raise SystemExit("ERROR: no se encontro lexiaHydrateOfficeResultPages; no se modifico el archivo.")

# 2) Restaurar el click original: usa la pagina ya resuelta/cacheada y no
#    fuerza apertura sin pagina (que terminaba mostrando pagina 1).
click_modified = nl("""          const effectivePath=path||requestedPath;

          // LEXIA_SEARCH_OFFICE_TEXT_PREVIEW: copiar el comportamiento de Investigacion.
          if(lexiaIsOfficeResult(effectivePath)){
            if(window.lexiaQuickViewerOpen){
              window.lexiaQuickViewerOpen(effectivePath,undefined,resultSnippet);
            }
            return;
          }

          if(
            resultSnippet &&
            lexiaIsOfficeResult(effectivePath) &&""")
click_original = nl("""          const effectivePath=path||requestedPath;

          if(
            resultSnippet &&
            lexiaIsOfficeResult(effectivePath) &&""")

if click_modified in text:
    text = text.replace(click_modified, click_original)
    print("OK: restaurado click Office con pagina correcta.")
elif click_original in text:
    print("OK: el click Office ya usa la logica original de pagina.")
else:
    raise SystemExit("ERROR: no se encontro el handler Office del Buscador; no se modifico el archivo.")

# 3) Si alguna variante llego a instalar la exclusion del capturador de pagina,
#    restaurarla tambien. En esta rama normalmente ese bloque no existe.
capture_modified = nl("""    const btn=ev.target.closest?.('.search-preview-file[data-page]');
    if(!btn)return;
    // LEXIA_SEARCH_OFFICE_SKIP_PAGE_CAPTURE: dejar Office al mismo visor de Investigacion.
    const officePath=decodeURIComponent(btn.dataset.path||'');
    const officeExt=(officePath.toLowerCase().match(/(\.[^.\\/]+)$/)||[])[1]||'';
    if(['.doc','.docx','.rtf','.odt'].includes(officeExt))return;
    const sourcePage=parseInt(btn.dataset.page||'0',10);""")
capture_original = nl("""    const btn=ev.target.closest?.('.search-preview-file[data-page]');
    if(!btn)return;
    const sourcePage=parseInt(btn.dataset.page||'0',10);""")

if capture_modified in text:
    text = text.replace(capture_modified, capture_original)
    print("OK: restaurado capturador de pagina Office.")
elif capture_original in text:
    print("OK: capturador de pagina ya estaba en su forma original.")
else:
    print("OK: esta version no usa FINAL PAGE PREVIEW; no hay nada que restaurar ahi.")

# Verificar que no queden las dos modificaciones que causaban la apertura en pagina 1.
remaining = [mark for mark in (MARK_HYDRATE, MARK_CLICK) if mark in text]
if remaining:
    raise SystemExit("ERROR: quedaron marcas del parche anterior; no se escribio el archivo: " + ", ".join(remaining))

if text == original:
    print("OK: la Opcion A ya estaba restaurada; no habia cambios pendientes.")
    raise SystemExit(0)

if not BACKUP.exists():
    shutil.copy2(TARGET, BACKUP)
    print(f"Backup del estado anterior: {BACKUP}")
else:
    print(f"Backup existente conservado: {BACKUP}")

out = text.encode("utf-8")
if has_bom:
    out = b"\xef\xbb\xbf" + out
TARGET.write_bytes(out)

print("OK: OPCION A RESTAURADA.")
print("LibreOffice vuelve a resolver las paginas Office durante la busqueda.")
print("El click usa la pagina precalculada para abrir rapido en la pagina correcta.")
print("Investigacion no fue modificada.")
