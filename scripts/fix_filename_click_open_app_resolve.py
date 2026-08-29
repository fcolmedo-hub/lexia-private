from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "app" / "ui2" / "index.html"
MARK = "LEXIA_FILENAME_CLICK_OPEN_APP_RESOLVE_20260829"

PATCH = r'''
<script>
/* LEXIA_FILENAME_CLICK_OPEN_APP_RESOLVE_20260829
   Buscador por nombre: click sobre un nombre de archivo => abrir en la
   aplicación predeterminada de Windows. Si el DOM no trae data-path, resuelve
   el archivo contra /api/search-filename usando el texto clickeado.
*/
(function(){
  if(window.__lexiaFilenameClickOpenResolveInstalled) return;
  window.__lexiaFilenameClickOpenResolveInstalled = true;

  const FILE_NAME_RE = /[^\\/:*?"<>|\r\n]+\.(pdf|doc|docx|rtf|odt|xls|xlsx|ods|txt|csv|md|html?|png|jpe?g|webp|gif|bmp)$/i;
  const FILE_NAME_IN_TEXT_RE = /[^\\/:*?"<>|\r\n]+\.(pdf|doc|docx|rtf|odt|xls|xlsx|ods|txt|csv|md|html?|png|jpe?g|webp|gif|bmp)/ig;

  function cleanText(s){
    return String(s || "").replace(/\s+/g, " ").trim();
  }

  function decodeMaybe(value){
    value = String(value || "").trim();
    if(!value) return "";
    try { return decodeURIComponent(value); } catch(_err) { return value; }
  }

  function findPathFromNode(start){
    let node = start;
    for(let depth = 0; node && depth < 12; depth++, node = node.parentElement){
      if(!node.dataset) continue;
      const ds = node.dataset;
      const candidates = [
        ds.path,
        ds.filePath,
        ds.documentPath,
        ds.openPath,
        ds.fullPath,
        ds.sourcePath,
        ds.resolvedPath
      ];
      for(const value of candidates){
        const path = decodeMaybe(value);
        if(path && /[\\/]/.test(path)) return path;
      }
    }
    return "";
  }

  function extractFileNameFromText(text){
    text = cleanText(text);
    if(!text) return "";
    if(FILE_NAME_RE.test(text)) return text;
    FILE_NAME_IN_TEXT_RE.lastIndex = 0;
    const matches = [...text.matchAll(FILE_NAME_IN_TEXT_RE)].map(m => cleanText(m[0]));
    if(!matches.length) return "";
    matches.sort((a,b) => b.length - a.length);
    return matches[0];
  }

  function findClickedFileName(target){
    let node = target;
    for(let depth = 0; node && depth < 5; depth++, node = node.parentElement){
      const own = cleanText(node.innerText || node.textContent || "");
      const name = extractFileNameFromText(own);
      if(name) return name;
    }
    return "";
  }

  async function openSystemFile(path){
    path = String(path || "").trim();
    if(!path) return false;
    const res = await fetch("/api/open-file", {
      method: "POST",
      headers: {"Content-Type":"application/json"},
      body: JSON.stringify({path})
    });
    const data = await res.json().catch(() => ({}));
    if(!res.ok || data.ok === false){
      const msg = data && data.error ? data.error : ("HTTP " + res.status);
      throw new Error(msg);
    }
    return true;
  }

  async function resolveFilenameToPath(filename){
    filename = cleanText(filename);
    if(!filename) return "";
    const res = await fetch("/api/search-filename", {
      method: "POST",
      headers: {"Content-Type":"application/json"},
      body: JSON.stringify({query: filename, limit: 10})
    });
    const data = await res.json().catch(() => ({}));
    if(!res.ok || data.ok === false) return "";
    const rows = Array.isArray(data.results) ? data.results : [];
    if(!rows.length) return "";

    const wanted = filename.toLowerCase();
    const exact = rows.filter(row => String(row.document_name || "").toLowerCase() === wanted);
    const chosen = exact.length === 1 ? exact[0] : (rows.length === 1 ? rows[0] : null);
    return chosen ? String(chosen.document_path || "") : "";
  }

  function shouldIgnore(target){
    if(!target || !target.closest) return true;
    if(target.closest("input, textarea, select, option")) return true;
    if(target.closest("button[data-action='preview'], .search-preview-file, [data-preview-page]")) return true;
    if(target.closest("button") && !extractFileNameFromText(target.innerText || target.textContent || "")) return true;
    return false;
  }

  document.addEventListener("click", async function(ev){
    const target = ev.target && ev.target.closest ? ev.target.closest("a,button,span,div,p,strong,em") : null;
    if(shouldIgnore(target)) return;

    let path = findPathFromNode(target);
    const filename = findClickedFileName(target);

    // Sólo actuar ante nombres de archivo reales o nodos con ruta explícita.
    if(!path && !filename) return;

    ev.preventDefault();
    ev.stopPropagation();
    ev.stopImmediatePropagation();

    try{
      if(!path) path = await resolveFilenameToPath(filename);
      if(!path){
        alert("No pude determinar de forma segura qué archivo abrir: " + filename);
        return;
      }
      await openSystemFile(path);
    }catch(err){
      alert("No se pudo abrir el archivo: " + (err && err.message ? err.message : err));
    }
  }, true);
})();
</script>
'''


def main() -> None:
    if not TARGET.exists():
        raise SystemExit(f"No existe {TARGET}")

    text = TARGET.read_text(encoding="utf-8", errors="replace")
    original = text

    if MARK in text:
        print("OK: el parche robusto ya estaba aplicado.")
        return

    if "</body>" not in text:
        raise SystemExit("No encontré </body> en index.html. No modifiqué el archivo.")

    backup = TARGET.with_suffix(".html.bak-filename-click-open-app-resolve")
    if not backup.exists():
        backup.write_text(original, encoding="utf-8")

    text = text.replace("</body>", PATCH + "\n</body>", 1)
    TARGET.write_text(text, encoding="utf-8")
    print("OK: parche robusto aplicado en app/ui2/index.html")
    print(f"Backup: {backup}")


if __name__ == "__main__":
    main()
