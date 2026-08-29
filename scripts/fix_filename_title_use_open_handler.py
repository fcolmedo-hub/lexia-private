from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "app" / "ui2" / "index.html"

OLD_CLASS = 'class="result-title result-title-btn search-preview-file"'
NEW_CLASS = 'class="result-title result-title-btn ${which===\'filename\'?\'search-open-file\':\'search-preview-file\'}"'

# Quita todos los listeners experimentales anteriores que intentaban interceptar
# clicks sobre el titulo. El titulo debe usar el mismo handler existente que Abrir.
SCRIPT_RE = re.compile(
    r"\n?<script>\s*/\*\s*(?:"
    r"LEXIA_FILENAME_CLICK_OPEN_APP_RESOLVE_20260829|"
    r"LEXIA_FILENAME_CLICK_OPEN_APP_20260829|"
    r"LEXIA_FILENAME_TITLE_CLICK_SAME_OPEN_BUTTON_20260829|"
    r"LEXIA_FILENAME_TITLE_CLICK_SAME_OPEN_BUTTON_V2_20260829"
    r")[\s\S]*?</script>\s*",
    re.MULTILINE,
)


def main() -> None:
    if not TARGET.exists():
        raise SystemExit(f"No existe {TARGET}")

    text = TARGET.read_text(encoding="utf-8", errors="replace")
    original = text

    # Eliminar intentos anteriores.
    text = SCRIPT_RE.sub("\n", text)

    if NEW_CLASS in text:
        print("OK: el titulo por nombre ya usa el handler real de Abrir.")
    else:
        count = text.count(OLD_CLASS)
        if count < 1:
            raise SystemExit(
                "No encontre el renderer esperado del titulo. No modifique index.html."
            )
        text = text.replace(OLD_CLASS, NEW_CLASS)
        print(f"OK: reemplazado renderer de titulo en {count} bloque(s).")

    if text == original:
        print("Sin cambios adicionales.")
        return

    backup = TARGET.with_suffix(".html.bak-filename-title-real-open-handler")
    if not backup.exists():
        backup.write_text(original, encoding="utf-8")

    TARGET.write_text(text, encoding="utf-8")
    print("OK: app/ui2/index.html actualizado.")
    print("En modo filename el titulo ahora tiene class search-open-file.")
    print("En modo professional conserva search-preview-file.")
    print(f"Backup: {backup}")


if __name__ == "__main__":
    main()
