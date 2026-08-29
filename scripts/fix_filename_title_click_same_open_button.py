from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "app" / "ui2" / "index.html"

PATCH = r'''
<script>
/* LEXIA_FILENAME_TITLE_CLICK_SAME_OPEN_BUTTON_V2_20260829
   Click sobre el nombre del archivo => ejecutar el mismo boton Abrir de la tarjeta.
*/
(function(){
  if(window.__lexiaFilenameTitleSameOpenButtonV2Installed) return;
  window.__lexiaFilenameTitleSameOpenButtonV2Installed = true;

  function textOf(el){
    return String((el && (el.innerText || el.textContent)) || "")
      .replace(/\s+/g, " ").trim();
  }

  function isFileNameText(txt){
    return /^[^\\/:*?"<>|]+\.(pdf|doc|docx|rtf|odt|xls|xlsx|ods|txt|csv|md|html?|png|jpe?g|webp|gif|bmp)$/i.test(txt);
  }

  function findExactFileTitle(start){
    let node = start;
    for(let depth=0; node && depth<8; depth++, node=node.parentElement){
      const txt = textOf(node);
      if(isFileNameText(txt)) return node;
    }
    return null;
  }

  function findOpenButton(start){
    let node = start;
    for(let depth=0; node && depth<14; depth++, node=node.parentElement){
      if(!node.querySelectorAll) continue;
      const buttons = Array.from(node.querySelectorAll("button"));
      const open = buttons.find(btn => textOf(btn).toLowerCase() === "abrir");
      if(open) return open;
    }
    return null;
  }

  document.addEventListener("click", function(ev){
    if(!ev.target || !ev.target.closest) return;
    if(ev.target.closest("button")) return;

    const title = findExactFileTitle(ev.target);
    if(!title) return;

    const openButton = findOpenButton(title);
    if(!openButton) return;

    ev.preventDefault();
    ev.stopPropagation();
    ev.stopImmediatePropagation();
    openButton.click();
  }, true);
})();
</script>
'''

SCRIPT_RE = re.compile(
    r"\n?<script>\s*/\*\s*(?:LEXIA_FILENAME_CLICK_OPEN_APP_RESOLVE_20260829|LEXIA_FILENAME_CLICK_OPEN_APP_20260829|LEXIA_FILENAME_TITLE_CLICK_SAME_OPEN_BUTTON_20260829|LEXIA_FILENAME_TITLE_CLICK_SAME_OPEN_BUTTON_V2_20260829)[\s\S]*?</script>\s*",
    re.MULTILINE,
)


def main() -> None:
    if not TARGET.exists():
        raise SystemExit(f"No existe {TARGET}")

    text = TARGET.read_text(encoding="utf-8", errors="replace")
    original = text
    text = SCRIPT_RE.sub("\n", text)

    if "</body>" not in text:
        raise SystemExit("No encontré </body> en index.html. No modifiqué el archivo.")

    text = text.replace("</body>", PATCH + "\n</body>", 1)

    backup = TARGET.with_suffix(".html.bak-filename-title-open-v2")
    if not backup.exists():
        backup.write_text(original, encoding="utf-8")

    TARGET.write_text(text, encoding="utf-8")
    print("OK: parche V2 aplicado en app/ui2/index.html")
    print(f"Backup: {backup}")


if __name__ == "__main__":
    main()
