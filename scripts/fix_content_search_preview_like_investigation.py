from __future__ import annotations

import re
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "app" / "ui2" / "index.html"
BACKUP = ROOT / "app" / "ui2" / "index.html.bak-before-office-preview-investigation-v2"

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


MARK_HYDRATE = "LEXIA_SEARCH_INVESTIGATION_V2_NO_PREFETCH"
MARK_MAIN = "LEXIA_SEARCH_INVESTIGATION_V2_OFFICE_TEXT"
MARK_CAPTURE = "LEXIA_SEARCH_INVESTIGATION_V2_CAPTURE_BYPASS"

# OBJETIVO
# -------
# Para DOC/DOCX/RTF/ODT del Buscador de contenido debemos entrar por la MISMA
# rama visual que usa Investigar cuando no fuerza pagina: texto extraido del
# documento + resaltado amarillo del snippet. Eso implica:
#   1) no precalcular data-preview-page;
#   2) no dejar que el handler capturador de [data-page] intercepte Office;
#   3) abrir Office con lexiaQuickViewerOpen(path, undefined, snippet).
# PDF y los demas formatos conservan su comportamiento paginado existente.

# ---------------------------------------------------------------------------
# 1) Desactivar el prefetch Office del Buscador.
# ---------------------------------------------------------------------------
hydrate_variants = [
    nl("""  function lexiaHydrateOfficeResultPages(box,which){
    if(which!=='professional'||!box)return;"""),
    nl("""  function lexiaHydrateOfficeResultPages(box,which){
    // LEXIA_SEARCH_OFFICE_NO_PREFETCH: Investigacion no precalcula paginas Office.
    return;
    if(which!=='professional'||!box)return;"""),
    nl("""  function lexiaHydrateOfficeResultPages(box,which){
    // LEXIA_SEARCH_EXACT_INVESTIGATION_NO_PREFETCH: Investigar no precalcula previewPage.
    return;
    if(which!=='professional'||!box)return;"""),
]
hydrate_v2 = nl(f"""  function lexiaHydrateOfficeResultPages(box,which){{
    // {MARK_HYDRATE}: Office no genera data-preview-page.
    return;
    if(which!=='professional'||!box)return;""")

if hydrate_v2 not in text:
    replaced = False
    for candidate in hydrate_variants:
        if candidate in text:
            text = text.replace(candidate, hydrate_v2, 1)
            replaced = True
            break
    if not replaced:
        raise SystemExit("ERROR: no se encontro lexiaHydrateOfficeResultPages; no se escribio index.html.")
    print("OK: prefetch Office desactivado.")
else:
    print("OK: prefetch Office ya estaba desactivado.")

# ---------------------------------------------------------------------------
# 2) Handler principal: Office SIEMPRE abre SIN pagina.
#    Si el parche anterior ya estaba aplicado, lo normalizamos.
# ---------------------------------------------------------------------------
old_main_patched = nl("""          const effectivePath=path||requestedPath;

          // LEXIA_SEARCH_EXACT_INVESTIGATION_MAIN
          // Mismo contrato que Investigar: path + page_start + snippet -> visor compartido.
          if(window.lexiaQuickViewerOpen){
            window.lexiaQuickViewerOpen(
              effectivePath,
              parseInt(prev.dataset.page||'0',10)||undefined,
              resultSnippet||''
            );
          }""")

main_v2 = nl(f"""          const effectivePath=path||requestedPath;

          // {MARK_MAIN}
          // Office entra por la misma vista textual de Investigar: SIN pagina.
          if(lexiaIsOfficeResult(effectivePath)){{
            delete prev.dataset.previewPage;
            if(window.lexiaQuickViewerOpen){{
              window.lexiaQuickViewerOpen(
                effectivePath,
                undefined,
                resultSnippet||''
              );
            }}else{{
              window.open(
                '/api/file-preview?path='+encodeURIComponent(effectivePath),
                '_blank',
                'noopener'
              );
            }}
            return;
          }}

          // Los PDF y demas formatos conservan la pagina del resultado.
          if(window.lexiaQuickViewerOpen){{
            window.lexiaQuickViewerOpen(
              effectivePath,
              parseInt(prev.dataset.page||'0',10)||undefined,
              resultSnippet||''
            );
          }}""")

if main_v2 not in text:
    if old_main_patched in text:
        text = text.replace(old_main_patched, main_v2, 1)
        print("OK: parche anterior corregido: Office ya no recibe page_start.")
    else:
        # Estado original/restaurado: quitar la rama que resuelve previewPage antes del visor.
        main_re = re.compile(
            r"(?P<indent>[ \t]*)const effectivePath=path\|\|requestedPath;\s*"
            r"if\(\s*resultSnippet\s*&&\s*lexiaIsOfficeResult\(effectivePath\)\s*&&\s*!prev\.dataset\.previewPage\s*\)\{\s*"
            r"try\{[\s\S]*?lexiaResolveOfficeResultPage\([\s\S]*?effectivePath,[\s\S]*?resultSnippet[\s\S]*?\);[\s\S]*?"
            r"lexiaSetOfficePreviewPage\(prev,page\);[\s\S]*?return;\s*\}catch\(_\)\{\}\s*\}\s*"
            r"if\(window\.lexiaQuickViewerOpen\)\{\s*"
            r"const isOffice=lexiaIsOfficeResult\(effectivePath\);\s*"
            r"const viewerPage=isOffice[\s\S]*?"
            r"window\.lexiaQuickViewerOpen\(\s*effectivePath,\s*viewerPage,\s*resultSnippet\s*\);\s*\}",
            re.MULTILINE,
        )
        match = main_re.search(text)
        if not match:
            raise SystemExit(
                "ERROR: no se encontro el handler principal del Buscador ni el parche anterior; "
                "no se escribio index.html."
            )
        indent = match.group("indent")
        replacement = main_v2.replace("          ", indent, 1)
        text = text[:match.start()] + replacement + text[match.end():]
        print("OK: handler principal Office cambiado a vista textual de Investigar.")
else:
    print("OK: handler principal Office ya usa vista textual de Investigar.")

# ---------------------------------------------------------------------------
# 3) Handler de captura [data-page]: Office debe PASAR DE LARGO.
#    Este listener corre antes que el handler principal; si no lo excluimos,
#    fuerza el flujo paginado y termina mostrando pagina 1.
# ---------------------------------------------------------------------------
capture_original = nl("""    const btn=ev.target.closest?.('.search-preview-file[data-page]');
    if(!btn)return;
    const sourcePage=parseInt(btn.dataset.page||'0',10);""")

capture_old = nl("""    const btn=ev.target.closest?.('.search-preview-file[data-page]');
    if(!btn)return;
    // LEXIA_SEARCH_OFFICE_SKIP_PAGE_CAPTURE: dejar Office al mismo visor de Investigacion.
    const officePath=decodeURIComponent(btn.dataset.path||'');
    const officeExt=(officePath.toLowerCase().match(/(\.[^.\\/]+)$/)||[])[1]||'';
    if(['.doc','.docx','.rtf','.odt'].includes(officeExt))return;
    const sourcePage=parseInt(btn.dataset.page||'0',10);""")

capture_v2 = nl(f"""    const btn=ev.target.closest?.('.search-preview-file[data-page]');
    if(!btn)return;
    // {MARK_CAPTURE}: Office no entra al capturador paginado.
    const officePath=decodeURIComponent(btn.dataset.path||'');
    const officeExt=(officePath.toLowerCase().match(/(\.[^.\\/]+)$/)||[])[1]||'';
    if(['.doc','.docx','.rtf','.odt'].includes(officeExt))return;
    const sourcePage=parseInt(btn.dataset.page||'0',10);""")

if capture_v2 not in text:
    if capture_old in text:
        text = text.replace(capture_old, capture_v2, 1)
        print("OK: bypass Office del handler capturador normalizado.")
    elif capture_original in text:
        text = text.replace(capture_original, capture_v2, 1)
        print("OK: Office excluido del handler capturador paginado.")
    else:
        raise SystemExit(
            "ERROR: no se encontro el handler capturador [data-page]; no se escribio index.html."
        )
else:
    print("OK: Office ya esta excluido del handler capturador paginado.")

# ---------------------------------------------------------------------------
# 4) Neutralizar una posible rama Office antigua DENTRO del capturador.
#    Deberia quedar inalcanzable por el bypass anterior, pero la dejamos tambien
#    sin capacidad de abrir una pagina si alguna variante cambia el orden.
# ---------------------------------------------------------------------------
old_capture_office_re = re.compile(
    r"(?P<indent>[ \t]*)if\(isOffice\)\{\s*"
    r"(?:\/\/[^\n]*\n\s*)?"
    r"(?:let previewPage=parseInt\(btn\.dataset\.previewPage\|\|'0',10\)\|\|0;[\s\S]*?)?"
    r"if\(window\.lexiaQuickViewerOpen\)\{[\s\S]*?"
    r"window\.lexiaQuickViewerOpen\([\s\S]*?\);[\s\S]*?\}\s*"
    r"(?:else\{[\s\S]*?\}\s*)?return;\s*\}",
    re.MULTILINE,
)

for match in list(old_capture_office_re.finditer(text))[::-1]:
    block = match.group(0)
    if MARK_MAIN in block or MARK_CAPTURE in block:
        continue
    if "isOffice" not in block or "lexiaQuickViewerOpen" not in block:
        continue
    indent = match.group("indent")
    replacement = nl(f"""{indent}if(isOffice){{
{indent}  // Office no debe abrirse desde el capturador paginado.
{indent}  return;
{indent}}}""")
    text = text[:match.start()] + replacement + text[match.end():]

# ---------------------------------------------------------------------------
# Verificacion fuerte antes de escribir.
# ---------------------------------------------------------------------------
for marker in (MARK_HYDRATE, MARK_MAIN, MARK_CAPTURE):
    if marker not in text:
        raise SystemExit(f"ERROR: falta {marker}; no se escribio index.html.")

if "LEXIA_SEARCH_EXACT_INVESTIGATION_MAIN" in text:
    # El parche v1 no puede quedar activo porque enviaba page_start a Office.
    raise SystemExit("ERROR: quedo activo el parche v1 que enviaba page_start; no se escribio index.html.")

required_call = nl("""              window.lexiaQuickViewerOpen(
                effectivePath,
                undefined,
                resultSnippet||''
              );""")
if required_call not in text:
    raise SystemExit("ERROR: Office no quedo configurado con pagina undefined; no se escribio index.html.")

if text == original:
    print("OK: no habia cambios pendientes.")
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

print("OK: CORRECCION V2 APLICADA.")
print("DOC/DOCX/RTF/ODT del Buscador ya no reciben ninguna pagina.")
print("El handler capturador [data-page] ignora Office.")
print("El visor entra por texto extraido + snippet, igual que Investigar, con resaltado amarillo.")
print("PDF conserva su apertura paginada normal.")
