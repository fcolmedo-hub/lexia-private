from __future__ import annotations
import os, platform, sys
from pathlib import Path

def project_root() -> Path:
    return Path(__file__).resolve().parents[2]

def runtime_dir() -> Path:
    value=os.environ.get('LEXIA_RUNTIME_DIR','').strip()
    return Path(value).expanduser().resolve() if value else project_root()/'runtime'

def data_dir() -> Path:
    value=os.environ.get('LEXIA_DATA_DIR','').strip()
    return Path(value).expanduser().resolve() if value else project_root()/'data'

def venv_python(root: Path|None=None) -> Path:
    root=(root or project_root()).resolve()
    return root/'.venv'/'Scripts'/'python.exe' if os.name=='nt' else root/'.venv'/'bin'/'python'

def ensure_project_on_syspath() -> Path:
    root=project_root()
    if str(root) not in sys.path: sys.path.insert(0,str(root))
    return root

def platform_name() -> str:
    return platform.system().lower()
