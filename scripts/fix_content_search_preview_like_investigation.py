from __future__ import annotations

import re
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "app" / "ui2" / "index.html"
BACKUP = ROOT / "app" / "ui2" / "index.html.bak-before-exact-investigation-office-preview"

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


MARK_HYDRATE = "LEXIA_SEARCH_EXACT_INVESTIGATION_NO_PREFETCH"
MARK_MAIN = "LEXIA_SEARCH_EXACT_INVESTIGATION_MAIN"
MARK_CAPTURE = "LEXIA_SEARCH_EXACT_INVESTIGATION_CAPTURE"

# INVESTIGAR abre una fuente con este contrato:
#   lexiaQuickViewerOpen(path, page, snippet)
# El propio visor compartido se ocupa de Office: convierte/cachea con LibreOffice
# y llama /api/office-preview-page con page como fallback + snippet para localizar
# la pagina real. El Buscador no debe volver a resolver otra previewPage antes.

# ---------------------------------------------------------------------------
# 1) Desactivar el prefetch Office exclusivo del Buscador.
#    Investigar no genera data-preview-page durante la busqueda.
# ---------------------------------------------------------------------------
hydrate_active = nl("""  function lexiaHydrateOfficeResultPages(box,which){
    if(which!=='professional'||!box)return;""")
hydrate_previous = nl("""  function lexiaHydrateOfficeResultPages(box,which){
    // LEXIA_SEARCH_OFFICE_NO_PREFETCH: Investigacion no precalcula paginas Office.
    return;
    if(which!=='professional'||!box)return;""")
hydrate_exact = nl(f"""  function lexiaHydrateOfficeResultPages(box,which){{
    // {MARK_HYDRATE}: Investigar no precalcula previewPage.
    return;
    if(which!=='professional'||!box)return;""")

if hydrate_exact in text:
    print("OK: prefetch Office del Buscador ya estaba desactivado como en Investigar.")
elif hydrate_previous in text:
    text = text.replace(hydrate_previous, hydrate_exact, 1)
    print("OK: prefetch Office del Buscador normalizado al flujo de Investigar.")
elif hydrate_active in text:
    text = text.replace(hydrate_active, hydrate_exact, 1)
    print("OK: prefetch Office del Buscador desactivado.")
else:
    raise SystemExit("ERROR: no se encontro lexiaHydrateOfficeResultPages; no se modifico index.html.")

# ---------------------------------------------------------------------------
# 2) Handler principal de .search-preview-file.
#    Quitar la resolucion anticipada de previewPage y pasar exactamente
#    effectivePath + page_start(data-page) + resultSnippet al visor compartido.
# ---------------------------------------------------------------------------
if MARK_MAIN not in text:
    main_re = re.compile(
        r"(?P<indent>[ \t]*)const effectivePath=path\|\|requestedPath;\s*"
        r"if\(\s*resultSnippet\s*&&\s*lexiaIsOfficeResult\(effectivePath\)\s*&&\s*!prev\.dataset\.previewPage\s*\)\{\s*"
        r"try\{[\s\S]*?lexiaResolveOfficeResultPage\([\s\S]*?effectivePath,[\s\S]*?resultSnippet[\s\S]*?\);[\s\S]*?return;\s*\}catch\(_\)\{\}\s*\}\s*"
        r"if\(window\.lexiaQuickViewerOpen\)\{\s*"
        r"const isOffice=lexiaIsOfficeResult\(effectivePath\);\s*"
        r"const viewerPage=isOffice[\s\S]*?"
        r"window\.lexiaQuickViewerOpen\(\s*effectivePath,\s*viewerPage,\s*resultSnippet\s*\);\s*\}",
        re.MULTILINE,
    )
    match = main_re.search(text)
    if not match:
        raise SystemExit(
            "ERROR: no se encontro el handler principal Office del Buscador; "
            "no se modifico index.html."
        )
    indent = match.group("indent")
    replacement = nl(
        f"""{indent}const effectivePath=path||requestedPath;

{indent}// {MARK_MAIN}
{indent}// Mismo contrato que Investigar: path + page_start + snippet -> visor compartido.
{indent}if(window.lexiaQuickViewerOpen){{
{indent}  window.lexiaQuickViewerOpen(
{indent}    effectivePath,
{indent}    parseInt(prev.dataset.page||'0',10)||undefined,
{indent}    resultSnippet||''
{indent}  );
{indent}}}"""
    )
    text = text[: match.start()] + replacement + text[match.end() :]
    print("OK: handler principal del Buscador = path + page_start + snippet, igual que Investigar.")
else:
    print("OK: handler principal ya usa el flujo exacto de Investigar.")

# ---------------------------------------------------------------------------
# 3) Handler capturador posterior.
#    Este era otro camino Office que volvia a leer data-preview-page o llamaba
#    /api/office-preview-page antes del visor. Se reemplaza por el mismo contrato
#    de Investigar para que no pueda sobrescribir la pagina.
# ---------------------------------------------------------------------------
if MARK_CAPTURE not in text:
    capture_re = re.compile(
        r"(?P<indent>[ \t]*)if\(isOffice\)\{\s*"
        r"let previewPage=parseInt\(btn\.dataset\.previewPage\|\|'0',10\)\|\|0;"
        r"[\s\S]*?"
        r"window\.lexiaQuickViewerOpen\(path,previewPage\|\|sourcePage,snippet\);"
        r"[\s\S]*?"
        r"return;\s*"
        r"\}",
        re.MULTILINE,
    )
    match = capture_re.search(text)
    if match:
        indent = match.group("indent")
        replacement = nl(
            f"""{indent}if(isOffice){{
{indent}  // {MARK_CAPTURE}
{indent}  // Copia literal del contrato de apertura de Investigar.
{indent}  if(window.lexiaQuickViewerOpen){{
{indent}    window.lexiaQuickViewerOpen(
{indent}      path,
{indent}      sourcePage>0 ? sourcePage : undefined,
{indent}      snippet||''
{indent}    );
{indent}  }}else{{
{indent}    window.open(
{indent}      '/api/file-preview?path='+encodeURIComponent(path),
{indent}      '_blank',
{indent}      'noopener'
{indent}    );
{indent}  }}
{indent}  return;
{indent}}}"""
        )
        text = text[: match.start()] + replacement + text[match.end() :]
        print("OK: segundo handler Office del Buscador copiado del flujo de Investigar.")
    else:
        # Algunas variantes no traen este capturador. Eso ya equivale a no
        # interferir con el visor compartido.
        print("OK: esta variante no tiene segundo handler Office que interfiera.")
else:
    print("OK: segundo handler Office ya usa el flujo exacto de Investigar.")

# ---------------------------------------------------------------------------
# Verificaciones antes de escribir.
# ---------------------------------------------------------------------------
required = [MARK_HYDRATE, MARK_MAIN]
missing = [mark for mark in required if mark not in text]
if missing:
    raise SystemExit(
        "ERROR: verificacion incompleta; no se escribio index.html: "
        + ", ".join(missing)
    )

# No puede quedar la rama principal que usa previewPage para elegir viewerPage.
if "const viewerPage=isOffice" in text:
    raise SystemExit(
        "ERROR: todavia existe viewerPage basado en previewPage; no se escribio index.html."
    )

if text == original:
    print("OK: VISTA PREVIA DEL BUSCADOR = INVESTIGAR; no habia cambios pendientes.")
    raise SystemExit(0)

if not BACKUP.exists():
    shutil.copy2(TARGET, BACKUP)
    print(f"Backup: {BACKUP}")
else:
    print(f"Backup existente conservado: {BACKUP}")

out = text.encode("utf-8")
if has_bom:
    out = b"\xef\xbb\xbf" + out
TARGET.write_bytes(out)

print("OK: VISTA PREVIA DEL BUSCADOR = INVESTIGAR.")
print("Office recibe path + page_start + snippet en lexiaQuickViewerOpen().")
print("La localizacion real de pagina queda exclusivamente en el visor compartido con LibreOffice.")
print("Investigacion no fue modificada.")
