from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "app" / "ui2" / "index.html"

OLD_MARKERS = (
    "LEXIA_FILENAME_CLICK_OPEN_APP_RESOLVE_20260829",
    "LEXIA_FILENAME_CLICK_OPEN_APP_20260829",
)
NEW_MARK = "LEXIA_FILENAME_TITLE_CLICK_SAME_OPEN_BUTTON_20260829"

PATCH = r'''
<script>
/* LEXIA_FILENAME_TITLE_CLICK_SAME_OPEN_BUTTON_20260829
   En resultados por nombre, click sobre el título del archivo => ejecutar
   el mismo botón Abrir que ya funciona en esa misma tarjeta/fila.
*/
(function(){
  if(window.__lexiaFilenameTitleSameOpenButtonInstalled) return;
  window.__lexiaFilenameTitleSameOpenButtonInstalled = true;

  function textOf(el){
    return String((el && (el.innerText || el.textContent)) || "").replace(/\s+/g, " ").trim();
  }

  function looksLikeFileTitle(el){
    const txt = textOf(el);
    if(!/\.(pdf|doc|docx|rtf|odt|xls|xlsx|ods|txt|csv|md|html?|png|jpe?g|webp|gif|bmp)$/i.test(txt)){
      return false;
    }
    // Evita actuar sobre la línea de ruta completa.
    if(/[\\/]/.test(txt)) return false;
    return true;
  }

  function findContainerWithOpenButton(start){
    let node = start;
    for(let depth = 0; node && depth < 10; depth++, node = node.parentElement){
      const buttons = Array.from(node.querySelectorAll ? node.querySelectorAll("button") : []);
      const openButton = buttons.find(btn => textOf(btn).toLowerCase() === "abrir");
      if(openButton) return {container: node, button: openButton};
    }
    return null;
  }

  document.addEventListener("click", function(ev){
    const target = ev.target && ev.target.closest
      ? ev.target.closest("a,button,span,strong,b,div,p")
      : null;
    if(!target) return;

    // Si ya tocó el botón Abrir, no intervenir.
    if(target.closest("button")) return;

    if(!looksLikeFileTitle(target)) return;

    const found = findContainerWithOpenButton(target);
    if(!found || !found.button) return;

    ev.preventDefault();
    ev.stopPropagation();
    ev.stopImmediatePropagation();

    found.button.click();
  }, true);
})();
</script>
'''

SCRIPT_RE = re.compile(
    r"\n?<script>\s*/\*\s*(?:LEXIA_FILENAME_CLICK_OPEN_APP_RESOLVE_20260829|LEXIA_FILENAME_CLICK_OPEN_APP_20260829)[\s\S]*?</script>\s*",
    re.MULTILINE,
)


def main() -> None:
    if not TARGET.exists():
        raise SystemExit(f"No existe {TARGET}")

    text = TARGET.read_text(encoding="utf-8", errors="replace")
    original = text

    # Quitar los intentos anteriores, porque interceptaban clicks y podían romper la tarjeta.
    text = SCRIPT_RE.sub("\n", text)

    if NEW_MARK not in text:
        if "</body>" not in text:
            raise SystemExit("No encontré </body> en index.html. No modifiqué el archivo.")
        text = text.replace("</body>", PATCH + "\n</body>", 1)

    if text == original:
        print("OK: index.html ya tenía sólo el parche correcto.")
        return

    backup = TARGET.with_suffix(".html.bak-filename-title-same-open-button")
    if not backup.exists():
        backup.write_text(original, encoding="utf-8")

    TARGET.write_text(text, encoding="utf-8")
    print("OK: parche aplicado en app/ui2/index.html")
    print("Quitados intentos anteriores si existían.")
    print(f"Backup: {backup}")


if __name__ == "__main__":
    main()
