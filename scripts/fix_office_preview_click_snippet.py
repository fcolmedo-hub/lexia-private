from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INDEX = ROOT / "app" / "ui2" / "index.html"

OLD = '''    const snippet=decodeURIComponent(btn.dataset.snippet||'');
'''

NEW = '''    let snippet=decodeURIComponent(btn.dataset.snippet||'');
    // LEXIA_OFFICE_CLICK_SNIPPET_20260828
    // Los resultados Office no siempre traen page_start ni data-snippet.
    // Si falta snippet, usamos el texto visible de la tarjeta para que
    // /api/office-preview-page pueda localizar la pagina dentro del PDF convertido.
    if(!snippet){
      const lexiaOfficeSnippetCard = btn.closest?.('.result-card,.source-card,.hit-card,article,li,div');
      if(lexiaOfficeSnippetCard){
        const lexiaOfficeSnippetClone = lexiaOfficeSnippetCard.cloneNode(true);
        try{
          lexiaOfficeSnippetClone.querySelectorAll('button,.result-meta,.source-meta,.actions,.lexiaOfficeDiag').forEach(n=>n.remove());
        }catch(_){ }
        snippet=String(lexiaOfficeSnippetClone.innerText||'')
          .replace(/\\s+/g,' ')
          .trim()
          .slice(0,1800);
      }
    }
'''


def backup_once(path: Path, suffix: str, text: str) -> Path:
    backup = path.with_suffix(path.suffix + suffix)
    if not backup.exists():
        backup.write_text(text, encoding="utf-8")
    return backup


def main() -> None:
    if not INDEX.exists():
        raise SystemExit(f"No existe {INDEX}")
    text = INDEX.read_text(encoding="utf-8", errors="replace")

    if "LEXIA_OFFICE_CLICK_SNIPPET_20260828" in text:
        print("OK: el fallback de snippet Office ya estaba aplicado.")
        return

    if OLD not in text:
        raise SystemExit("No encontré la línea exacta const snippet=decodeURIComponent(...). No modifiqué index.html.")

    new_text = text.replace(OLD, NEW, 1)
    backup = backup_once(INDEX, ".bak-office-click-snippet", text)
    INDEX.write_text(new_text, encoding="utf-8")
    print("OK: vista previa Office ahora usa el texto visible del resultado cuando falta snippet.")
    print(f"Backup index.html: {backup}")
    print("Reiniciá LexIA y recargá el navegador con Cmd+Shift+R.")


if __name__ == "__main__":
    main()
