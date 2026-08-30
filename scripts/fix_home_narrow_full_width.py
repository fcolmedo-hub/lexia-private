from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CSS = ROOT / "app" / "ui2" / "assets" / "responsive_shell.css"
MARK = "LEXIA_HOME_NARROW_FULL_WIDTH_20260830"
BLOCK = r'''

/* LEXIA_HOME_NARROW_FULL_WIDTH_20260830
   En modo drawer #home debe ocupar todo el viewport. El selector por ID
   evita que reglas históricas #home con calc(100vw - sidebar) ganen sobre
   la capa responsive basada sólo en .home. */
@media (max-width:900px){
  #home{
    margin-left:0!important;
    width:100vw!important;
    max-width:100vw!important;
    min-width:0!important;
    padding-left:0!important;
    padding-right:0!important;
    overflow-x:hidden!important;
  }
  #home .home-real,
  #home .hr-main,
  #home .hr-content{
    width:100%!important;
    max-width:100%!important;
    min-width:0!important;
    margin-left:0!important;
    margin-right:0!important;
    box-sizing:border-box!important;
  }
  #home .hr-main{display:block!important}
  #home .hr-content{padding-left:18px!important;padding-right:18px!important}
}

@media (max-width:560px){
  #home .hr-content{padding-left:10px!important;padding-right:10px!important}
}
'''

text = CSS.read_text(encoding="utf-8")
if MARK in text:
    print("OK: la correccion de ancho ya estaba aplicada")
else:
    backup = CSS.with_suffix(".css.bak-home-narrow-full-width")
    if not backup.exists():
        backup.write_text(text, encoding="utf-8")
    CSS.write_text(text.rstrip() + BLOCK + "\n", encoding="utf-8")
    print("OK: #home ahora usa el 100% del viewport en modo angosto")
