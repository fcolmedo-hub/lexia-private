from __future__ import annotations
import os, subprocess, sys, webbrowser
from pathlib import Path
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
if str(ROOT) not in sys.path: sys.path.insert(0,str(ROOT))
from app.ui2.portability import venv_python

# Garantiza que la vista previa Office del Buscador use el mismo visor que
# Investigación. La inyección es idempotente y no altera el código de
# Investigación ni el comportamiento de PDF/imágenes.
INDEX=HERE/'index.html'
SEARCH_PREVIEW_SCRIPT='search_preview_investigation.js'
SEARCH_PREVIEW_TAG=f'<script src="{SEARCH_PREVIEW_SCRIPT}?v=1"></script>'
try:
    html=INDEX.read_text(encoding='utf-8')
    if SEARCH_PREVIEW_SCRIPT not in html:
        if '</body>' in html:
            html=html.replace('</body>',SEARCH_PREVIEW_TAG+'\n</body>',1)
        else:
            html+='\n'+SEARCH_PREVIEW_TAG+'\n'
        INDEX.write_text(html,encoding='utf-8')
except Exception as exc:
    print('Aviso: no se pudo instalar el ajuste de vista previa del Buscador:',exc)

PORT=os.environ.get('LEXIA_UI2_PORT','8512')
URL=f'http://127.0.0.1:{PORT}'
py=venv_python(ROOT)
if not py.exists():
    raise SystemExit(f'No se encontró el Python del entorno virtual: {py}')
print('LexIA UI2 3.1.1 Portable')
print('Proyecto:',ROOT)
print('UI2:',URL)
try: webbrowser.open(URL)
except Exception: pass
env=os.environ.copy(); env['LEXIA_UI2_PORT']=PORT
raise SystemExit(subprocess.call([str(py),str(HERE/'server.py')],cwd=str(ROOT),env=env))
