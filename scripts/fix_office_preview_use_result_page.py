from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INDEX = ROOT / "app" / "ui2" / "index.html"

MARKER = "LEXIA_OFFICE_RESULT_PAGE_FALLBACK_20260828"

PREFETCH_OLD = '''  async function lexiaResolveOfficeResultPage(path,snippet){
    const url=
      '/api/office-preview-page?path='+encodeURIComponent(path)+
      '&snippet='+encodeURIComponent(String(snippet||''));
    const res=await fetch(url,{cache:'no-store'});
    const data=await res.json();
    if(!res.ok||!data.ok||!Number(data.page)){
      throw new Error(data.error||`HTTP ${res.status}`);
    }
    return Number(data.page);
  }
'''

PREFETCH_NEW = '''  async function lexiaResolveOfficeResultPage(path,snippet){
    // LEXIA_OFFICE_NO_PREFETCH_20260828
    // No convertir documentos Office durante busquedas/listados.
    return 0;
  }
'''

ANCHOR_OLD = '''      if(isOffice){
        let previewPage=parseInt(btn.dataset.previewPage||'0',10)||0;
'''

ANCHOR_NEW = '''      if(isOffice){
        // LEXIA_OFFICE_RESULT_PAGE_FALLBACK_20260828
        // Para Office, si el backend no localiza el pasaje y devuelve pag. 1,
        // conservar la pagina que ya muestra el resultado de busqueda.
        const metaText=String(card?.querySelector?.('.result-meta')?.textContent||card?.innerText||'');
        const metaPageMatch=metaText.match(/p[áa]g\.?\s*(\d+)/i);
        const officeSourcePage=(Number(sourcePage)>1?Number(sourcePage):(metaPageMatch?Number(metaPageMatch[1]):(Number(sourcePage)||1)));
        let previewPage=parseInt(btn.dataset.previewPage||'0',10)||0;
        if(previewPage<2){
          previewPage=0;
          try{ delete btn.dataset.previewPage; }catch(_){}
        }
'''

CLICK_META_OLD = '''            const u=
              '/api/office-preview-page?path='+encodeURIComponent(path)+
              '&snippet='+encodeURIComponent(String(snippet||''));
'''

CLICK_META_CONVERT = '''            const u=
              '/api/office-preview-page?path='+encodeURIComponent(path)+
              '&snippet='+encodeURIComponent(String(snippet||''))+
              '&convert=1';
'''

CLICK_META_SOURCE = '''            const u=
              '/api/office-preview-page?path='+encodeURIComponent(path)+
              '&fallback='+encodeURIComponent(String(sourcePage||''))+
              '&snippet='+encodeURIComponent(String(snippet||''))+
              '&convert=1';
'''

CLICK_META_NEW = '''            const u=
              '/api/office-preview-page?path='+encodeURIComponent(path)+
              '&fallback='+encodeURIComponent(String(officeSourcePage||''))+
              '&snippet='+encodeURIComponent(String(snippet||''))+
              '&convert=1';
'''

ASSIGN_OLD = '''              previewPage=Number(data.page);
              btn.dataset.previewPage=String(previewPage);
'''

ASSIGN_NEW = '''              const calculatedPage=Number(data.page)||0;
              previewPage=(calculatedPage>1?calculatedPage:officeSourcePage);
              btn.dataset.previewPage=String(previewPage);
'''

OPEN_VARIANTS = [
    "window.lexiaQuickViewerOpen(path,previewPage||sourcePage,snippet);",
    "window.lexiaQuickViewerOpen(path,((previewPage&&previewPage>1)?previewPage:sourcePage)||1,snippet);",
]

OPEN_NEW = "window.lexiaQuickViewerOpen(path,((previewPage&&previewPage>1)?previewPage:officeSourcePage)||1,snippet);"


def backup_once(path: Path, suffix: str, text: str) -> Path:
    backup = path.with_suffix(path.suffix + suffix)
    if not backup.exists():
        backup.write_text(text, encoding="utf-8")
    return backup


def main() -> None:
    if not INDEX.exists():
        raise SystemExit(f"No existe {INDEX}")

    text = INDEX.read_text(encoding="utf-8", errors="replace")
    original = text

    if "LEXIA_OFFICE_NO_PREFETCH_20260828" not in text and PREFETCH_OLD in text:
        text = text.replace(PREFETCH_OLD, PREFETCH_NEW, 1)

    if MARKER not in text:
        if ANCHOR_OLD not in text:
            raise SystemExit("No encontré el bloque exacto del click Office. No modifiqué index.html.")
        text = text.replace(ANCHOR_OLD, ANCHOR_NEW, 1)

    for old in (CLICK_META_SOURCE, CLICK_META_CONVERT, CLICK_META_OLD):
        if old in text:
            text = text.replace(old, CLICK_META_NEW, 1)
            break

    if ASSIGN_OLD in text:
        text = text.replace(ASSIGN_OLD, ASSIGN_NEW, 1)
    elif ASSIGN_NEW in text:
        pass
    else:
        print("AVISO: no encontré la asignación previewPage=Number(data.page).")

    for old in OPEN_VARIANTS:
        if old in text:
            text = text.replace(old, OPEN_NEW, 1)
            break

    if text == original:
        print("OK: index.html ya tenía aplicado el fallback de página visible para Office.")
        return

    backup = backup_once(INDEX, ".bak-office-result-page", original)
    INDEX.write_text(text, encoding="utf-8")
    print("OK: vista previa Office usará la página visible del resultado cuando el cálculo devuelva 1.")
    print(f"Backup index.html: {backup}")


if __name__ == "__main__":
    main()
