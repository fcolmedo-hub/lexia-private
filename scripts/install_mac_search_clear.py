#!/usr/bin/env python3
"""Agrega Limpiar al buscador de LexIA Mac sin reemplazar otros cambios locales."""
from __future__ import annotations

import argparse
from datetime import datetime
import os
from pathlib import Path
import shutil
import sys
import tempfile


TARGET = Path("app/ui2/index.html")
MARKER = "window.lexiaSearch320Clear=clearSearch;"


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise ValueError(f"{label}: se esperaba un bloque único, se encontraron {count}; se conservó index.html")
    return text.replace(old, new, 1)


def updated_html(original: str) -> str:
    if MARKER in original:
        return original
    text = original
    text = replace_once(text,
        "  const state={filename:{query:'',data:null},professional:{query:'',data:null}};\n  let mode='filename';",
        "  const state={filename:{query:'',data:null},professional:{query:'',data:null}};\n"
        "  const searchVersion={filename:0,professional:0};\n  let mode='filename';",
        "Estado de búsqueda")
    text = replace_once(text, "  async function refreshHistory(){", """  function clearSearch({all=false,focus=false}={}){
    const modes=all||mode==='navigator'?['filename','professional']:[mode];
    modes.forEach(item=>{
      searchVersion[item]++;
      state[item]={query:'',data:null};
    });
    const input=queryEl();
    if(input){input.value='';if(focus)input.focus();}
    const home=document.getElementById('homeQuickSearchInput');
    if(home)home.value='';
    document.getElementById('searchRecentHistory')?.classList.remove('open');
    const box=resultsEl();
    if(box)box.innerHTML='<div class="search-results-empty">Todavía no hay una búsqueda ejecutada en esta pestaña.</div>';
    const summary=document.getElementById('realSearchSummary');
    if(summary)summary.innerHTML='<strong>0 resultados</strong>';
    const prior=document.getElementById('realSearchQuery');
    if(prior)prior.textContent='Ingresá una consulta y presioná Buscar';
  }

  async function refreshHistory(){""", "Limpiar búsqueda")
    text = replace_once(text,
        "    if(!query)return;\n\n    window.lexiaSearch321b2BeforeSearch?.();",
        "    if(!query)return;\n    const requestVersion=++searchVersion[searchMode];\n\n    window.lexiaSearch321b2BeforeSearch?.();",
        "Versión de búsqueda")
    text = replace_once(text,
        "      state[searchMode]={query,data,filterKey:searchFilterKey};",
        "      if(requestVersion!==searchVersion[searchMode])return;\n"
        "      state[searchMode]={query,data,filterKey:searchFilterKey};",
        "Respuesta pendiente")
    text = replace_once(text,
        "    }catch(err){\n      if(mode===searchMode&&box)box.innerHTML=`<div class=\"search-error\"><b>No se pudo ejecutar la búsqueda.</b><br>${esc(err.message||err)}</div>`;",
        "    }catch(err){\n      if(requestVersion!==searchVersion[searchMode])return;\n"
        "      if(mode===searchMode&&box)box.innerHTML=`<div class=\"search-error\"><b>No se pudo ejecutar la búsqueda.</b><br>${esc(err.message||err)}</div>`;",
        "Error de búsqueda pendiente")
    text = replace_once(text,
        "    setMode('filename');\n  },{once:true});",
        """    const input=queryEl();
    input?.removeAttribute('value');
    const run=document.getElementById('runLegalSearch');
    if(run&&!document.getElementById('clearLegalSearch')){
      const clear=document.createElement('button');
      clear.id='clearLegalSearch';clear.type='button';clear.className='secondary';
      clear.textContent='Limpiar';clear.setAttribute('aria-label','Limpiar búsqueda');
      clear.style.cssText='height:46px;padding:0 13px;white-space:nowrap;flex:0 0 auto';
      run.before(clear);
      clear.addEventListener('click',event=>{
        event.preventDefault();event.stopPropagation();clearSearch({all:true,focus:true});
      });
    }
    setMode('filename');
  },{once:true});""", "Botón Limpiar")
    text = replace_once(text,
        "    if(ev.target?.id==='legalQuery')closeRecentHistory();\n  },true);",
        "    if(ev.target?.id==='legalQuery'){\n"
        "      closeRecentHistory();\n"
        "      if(!ev.target.value.trim())clearSearch();\n"
        "    }\n  },true);",
        "Borrado manual")
    text = replace_once(text,
        "  window.lexiaSearch320Run=runSearch;\n  window.lexiaSearch320SetMode=setMode;",
        "  window.lexiaSearch320Run=runSearch;\n  window.lexiaSearch320Clear=clearSearch;\n  window.lexiaSearch320SetMode=setMode;",
        "API de limpieza")
    return text


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Comprobar sin escribir")
    args = parser.parse_args()
    path = Path.cwd() / TARGET
    try:
        if not path.is_file() or path.is_symlink():
            raise ValueError(f"No se encontró un archivo regular: {path}")
        original = path.read_bytes()
        bom = original.startswith(b"\xef\xbb\xbf")
        decoded = original.decode("utf-8-sig")
        crlf = decoded.count("\r\n") > decoded.count("\n") - decoded.count("\r\n")
        normalized = decoded.replace("\r\n", "\n")
        updated = updated_html(normalized)
        if updated == normalized:
            print("El botón Limpiar ya está instalado. No se modificó LexIA.")
            return 0
        if args.check:
            print("Comprobación correcta: index.html admite la corrección. No se modificó LexIA.")
            return 0
        backup = path.with_name(path.name + ".respaldo-busqueda-" + datetime.now().strftime("%Y%m%d-%H%M%S-%f"))
        shutil.copy2(path, backup)
        data = (("\ufeff" if bom else "") + (updated.replace("\n", "\r\n") if crlf else updated)).encode("utf-8")
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(dir=path.parent,prefix="lexia-search-",suffix=".tmp",delete=False) as stream:
                temporary = Path(stream.name)
                stream.write(data)
            os.replace(temporary,path)
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
        print(f"Búsqueda actualizada. Respaldo: {backup}")
        print("Cerrá LexIA completamente y volvé a abrirla. No hace falta reconstruir la aplicación.")
        return 0
    except (OSError,ValueError,UnicodeError) as exc:
        print(f"No se modificó LexIA: {exc}",file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
