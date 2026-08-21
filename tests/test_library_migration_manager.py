import importlib.util
import sys
from pathlib import Path

def module():
    p=Path("tools/lexia_library_migrate.py")
    spec=importlib.util.spec_from_file_location("lm",p)
    m=importlib.util.module_from_spec(spec); sys.modules[spec.name]=m; spec.loader.exec_module(m); return m

def test_metadata_reclassification():
    m=module()
    raw='{"classification":{"document_type":"Contratos","confidence":0.81},"court":"CSJN"}'
    data=m.json.loads(m.rewrite_metadata(raw,"Jurisprudencia"))
    assert data["classification"]["document_type"]=="Jurisprudencia"
    assert data["classification"]["confidence"]==1.0
    assert data["classification"]["source"]=="physical_folder"
    assert data["court"]=="CSJN"

def test_protected_roots():
    m=module()
    assert {"Jurisprudencia","Escritos","Doctrina"} <= m.PROTECTED_ROOTS
