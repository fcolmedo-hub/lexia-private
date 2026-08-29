from __future__ import annotations

import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "app" / "ui2" / "index.html"
BACKUP = ROOT / "app" / "ui2" / "index.html.bak-before-office-preview-investigation-v3"

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

MARK_RENDER = "LEXIA_SEARCH_INVESTIGATION_V3_RENDER_NO_PAGE"
MARK_MAIN = "LEXIA_SEARCH_INVESTIGATION_V3_MAIN_TEXT"
MARK_CAPTURE = "LEXIA_SEARCH_INVESTIGATION_V3_CAPTURE_BYPASS"
MARK_HYDRATE = "LEXIA_SEARCH_INVESTIGATION_V3_NO_PREFETCH"

# 1) El renderer no debe asignar data-page a Office.
render_old = (
    '${which===\'professional\'&&r.page_start?` data-page="${esc(r.page_start)}"`:\'\'}'
)
render_new = (
    '${which===\'professional\'&&r.page_start&&!lexiaIsOfficeResult(r.document_path||\'\')'
    '?` data-page="${esc(r.page_start)}"`:\'\'}'
)

if MARK_RENDER not in text:
    count = text.count(render_old)
    if count < 1:
        if render_new in text:
            print("OK: renderer Office ya no genera data-page.")
        else:
            raise SystemExit(
                "ERROR: no se encontro el atributo data-page del renderer; "
                "no se escribio index.html."
            )
    else:
        text = text.replace(render_old, render_new, 1)
        needle = '<button class="result-title result-title-btn search-preview-file"'
        pos = text.find(needle)
        if pos >= 0:
            text = text[:pos] + f'<!-- {MARK_RENDER} -->' + text[pos:]
        print("OK: resultados Office ya no nacen con data-page.")
else:
    print("OK: renderer Office ya estaba corregido.")

# 2) Guard Office al principio del handler principal.
if MARK_MAIN not in text:
    anchor = "          const effectivePath=path||requestedPath;"
    pos = text.find(anchor)
    if pos < 0:
        raise SystemExit(
            "ERROR: no se encontro effectivePath en el handler principal; "
            "no se escribio index.html."
        )
    insert_at = pos + len(anchor)
    guard = nl(f'''\n\n          // {MARK_MAIN}\n          // Igual que Investigación para Office: texto extraido + snippet.\n          if(lexiaIsOfficeResult(effectivePath)){{\n            prev.removeAttribute('data-page');\n            prev.removeAttribute('data-preview-page');\n            if(window.lexiaQuickViewerOpen){{\n              window.lexiaQuickViewerOpen(\n                effectivePath,\n                undefined,\n                resultSnippet||''\n              );\n            }}else{{\n              window.open(\n                '/api/file-preview?path='+encodeURIComponent(effectivePath),\n                '_blank',\n                'noopener'\n              );\n            }}\n            return;\n          }}''')
    text = text[:insert_at] + guard + text[insert_at:]
    print("OK: handler principal Office conectado a vista textual de Investigación.")
else:
    print("OK: handler principal Office ya estaba conectado a vista textual.")

# 3) FINAL PAGE PREVIEW debe ignorar Office.
capture_anchor = nl('''    const btn=ev.target.closest?.('.search-preview-file[data-page]');\n    if(!btn)return;''')
capture_guard = nl(f'''    const btn=ev.target.closest?.('.search-preview-file[data-page]');\n    if(!btn)return;\n    // {MARK_CAPTURE}\n    const officePath=decodeURIComponent(btn.dataset.path||'');\n    const officeExt=(officePath.toLowerCase().match(/(\\.[^.\\\\/]+)$/)||[])[1]||'';\n    if(['.doc','.docx','.rtf','.odt'].includes(officeExt))return;''')

if MARK_CAPTURE not in text:
    if capture_anchor not in text:
        raise SystemExit(
            "ERROR: no se encontro FINAL PAGE PREVIEW; no se escribio index.html."
        )
    text = text.replace(capture_anchor, capture_guard, 1)
    print("OK: FINAL PAGE PREVIEW ignora Office.")
else:
    print("OK: FINAL PAGE PREVIEW ya ignoraba Office.")

# 4) Desactivar el prefetch Office propio del Buscador.
hydrate_decl = "  function lexiaHydrateOfficeResultPages(box,which){"
if MARK_HYDRATE not in text:
    pos = text.find(hydrate_decl)
    if pos < 0:
        raise SystemExit(
            "ERROR: no se encontro lexiaHydrateOfficeResultPages; "
            "no se escribio index.html."
        )
    insert_at = pos + len(hydrate_decl)
    text = text[:insert_at] + nl(f'''\n    // {MARK_HYDRATE}\n    return;''') + text[insert_at:]
    print("OK: prefetch Office del Buscador desactivado.")
else:
    print("OK: prefetch Office ya estaba desactivado.")

# 5) Verificaciones fuertes.
for marker in (MARK_RENDER, MARK_MAIN, MARK_CAPTURE, MARK_HYDRATE):
    if marker not in text:
        raise SystemExit(f"ERROR: falta {marker}; no se escribio index.html.")

if render_old in text:
    raise SystemExit(
        "ERROR: el renderer todavia genera data-page para Office; "
        "no se escribio index.html."
    )

required_guard = nl('''              window.lexiaQuickViewerOpen(\n                effectivePath,\n                undefined,\n                resultSnippet||''\n              );''')
if required_guard not in text:
    raise SystemExit(
        "ERROR: Office no quedo conectado a pagina undefined + snippet; "
        "no se escribio index.html."
    )

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

print("OK: CORRECCION V3 APLICADA.")
print("Office ya no genera data-page en el Buscador.")
print("FINAL PAGE PREVIEW no puede interceptar DOC/DOCX/RTF/ODT.")
print("Office abre por texto extraido + snippet, con el mismo resaltado amarillo de Investigación.")
print("PDF conserva data-page y su vista paginada.")
