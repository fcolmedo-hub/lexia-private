"""Apply reviewed UI changes in the served page; leave index.html on disk untouched."""
from functools import lru_cache
from hashlib import sha256
from pathlib import Path

MARKER = "window.lexiaSearch320Clear=clearSearch;"

def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise ValueError(f"{label}: se esperaba un bloque único, se encontraron {count}; se conservó index.html")
    return text.replace(old, new, 1)

def clear_search_html(original: str) -> str:
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

@lru_cache(maxsize=2)
def render_index(original: str) -> str:
    text = clear_search_html(original)
    start, end = "  const study=replace('startStudy',", "\n  replace('copyContext',"
    if text.count(start) != 1 or text.count(end) != 1:
        raise ValueError("No se reconoce el controlador de Estudiar. Se conservó index.html.")
    first, last = text.index(start), text.index(end)
    if last <= first:
        raise ValueError("El controlador de Estudiar tiene una estructura diferente.")
    if sha256(text[first:last].encode("utf-8")).hexdigest() not in {'9a2968650107bd50bcf5ea551682ca665ff967e81fc39b2461aadb6e125c3422', 'deb7116be252e4e5be087ab358cc9cffeae82801bbe1d4076d32080e81081534', '1f54b69b987090482aefb5c9980e79723af4282266cf8e0ab853f96cf4e86bf0'}:
        raise ValueError("El controlador de Estudiar tiene cambios locales diferentes.")
    replacement = (Path(__file__).parent / "assets/windows_study_confirmation.js").read_text(encoding="utf-8")
    return text[:first] + replacement + text[last:]
