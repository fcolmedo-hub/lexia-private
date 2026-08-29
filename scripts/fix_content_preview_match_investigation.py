from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INDEX = ROOT / "app" / "ui2" / "index.html"

MARKER = "LEXIA_CONTENT_PREVIEW_MATCH_INVESTIGATION_20260829"

# En Buscar > Contenido existia una rama especial para Office que antes de abrir
# consultaba /api/office-preview-page y usaba data-preview-page. Investigacion no
# hace eso: pasa path + page + snippet directamente al visor compartido.
OFFICE_BRANCH_RE = re.compile(
    r"(?P<indent>[ \t]*)if\(isOffice\)\{\s*"
    r"let previewPage=parseInt\(btn\.dataset\.previewPage\|\|'0',10\)\|\|0;"
    r"[\s\S]*?"
    r"window\.lexiaQuickViewerOpen\(path,previewPage\|\|sourcePage,snippet\);"
    r"[\s\S]*?"
    r"return;\s*"
    r"\}",
    re.MULTILINE,
)


def main() -> None:
    if not INDEX.exists():
        raise SystemExit(f"No existe {INDEX}")

    text = INDEX.read_text(encoding="utf-8", errors="replace")
    original = text

    if MARKER in text:
        print("OK: Buscar > Contenido ya usa el mismo flujo de apertura que Investigacion.")
        return

    match = OFFICE_BRANCH_RE.search(text)
    if not match:
        raise SystemExit(
            "No encontre la rama Office esperada del click de search-preview-file. "
            "No modifique index.html."
        )

    indent = match.group("indent")
    replacement = f'''{indent}if(isOffice){{
{indent}  // {MARKER}
{indent}  // Igual que Investigacion: no calcular otra pagina antes de abrir.
{indent}  // El visor comun recibe ruta + pagina del resultado + fragmento.
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
{indent}}}'''

    text = text[:match.start()] + replacement + text[match.end():]

    backup = INDEX.with_suffix(".html.bak-content-preview-match-investigation")
    if not backup.exists():
        backup.write_text(original, encoding="utf-8")

    INDEX.write_text(text, encoding="utf-8")

    print("OK: app/ui2/index.html actualizado.")
    print("Buscar > Contenido ahora abre Office con el mismo flujo que Investigacion:")
    print("path + page_start + snippet -> lexiaQuickViewerOpen().")
    print("La conversion DOC/DOCX/RTF/ODT sigue a cargo del visor compartido mediante LibreOffice.")
    print(f"Backup: {backup}")


if __name__ == "__main__":
    main()
