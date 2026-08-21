#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import argparse, json, sqlite3, sys
from pathlib import Path

def ro(path):
    c=sqlite3.connect(path.resolve().as_uri()+"?mode=ro",uri=True)
    c.row_factory=sqlite3.Row
    c.execute("PRAGMA query_only=ON")
    return c

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("root",nargs="?",default=r"D:\LexIA_2.3_DEV")
    a=ap.parse_args()
    root=Path(a.root).resolve()
    sys.path.insert(0,str(root))
    from config.settings import SETTINGS

    sp=Path(SETTINGS.autosync_state_path)
    cp=Path(SETTINGS.catalog_path)
    op=Path(SETTINGS.ocr_queue_path)

    print("# LEXIA — DIAGNOSTICO ESTADO AUTOSYNC v1.0 (SOLO LECTURA)")
    print("AutoSync state:",sp,"| existe:",sp.exists())
    print("Catalogo:",cp,"| existe:",cp.exists())
    print("OCR queue:",op,"| existe:",op.exists())
    print()

    state={}
    if sp.exists():
        try:
            state=json.loads(sp.read_text(encoding="utf-8"))
        except Exception as e:
            print("ERROR leyendo autosync_state:",repr(e))

    print("ESTADO AUTOSYNC PERSISTIDO")
    for k,v in state.items():
        print(f"  {k}: {v}")
    print()

    extraction=[]
    if cp.exists():
        c=ro(cp)
        try:
            extraction=[dict(r) for r in c.execute("""
                SELECT name,path,extraction_error,updated_at
                FROM documents
                WHERE COALESCE(is_deleted,0)=0
                  AND extraction_error IS NOT NULL
                  AND trim(extraction_error)<>''
                ORDER BY datetime(updated_at) DESC
                LIMIT 20
            """).fetchall()]
        finally:
            c.close()

    print("ERRORES DE EXTRACCION")
    print("  cantidad:",len(extraction))
    for r in extraction:
        print(" ",r["name"],"|",r["extraction_error"])
    if not extraction: print("  [ninguno]")
    print()

    ocr_summary={}
    ocr_errors=[]
    ocr_pending=[]
    if op.exists():
        c=ro(op)
        try:
            tabs=[r["name"] for r in c.execute("select name from sqlite_master where type='table'")]
            target=None
            for t in tabs:
                cols=[r["name"] for r in c.execute("pragma table_info("+t+")")]
                if "status" in [x.lower() for x in cols]:
                    target=(t,cols); break
            if target:
                t,cols=target
                low={x.lower():x for x in cols}
                sc=low["status"]
                pc=next((low[x] for x in ("document_path","path","file_path") if x in low),None)
                nc=next((low[x] for x in ("document_name","name","filename") if x in low),None)
                ec=next((low[x] for x in ("error","last_error") if x in low),None)

                for r in c.execute(f"select {sc} status,count(*) n from {t} group by {sc}"):
                    ocr_summary[str(r["status"])]=int(r["n"])

                selects=[f"{sc} status"]
                if pc: selects.append(f"{pc} document_path")
                if nc: selects.append(f"{nc} document_name")
                if ec: selects.append(f"{ec} error")
                rows=[dict(r) for r in c.execute(f"select {','.join(selects)} from {t}")]
                ocr_errors=[r for r in rows if str(r.get("status","")).lower()=="error"][:20]
                ocr_pending=[r for r in rows if str(r.get("status","")).lower() in ("pending","processing","queued")][:20]
        finally:
            c.close()

    print("OCR RESUMEN:",ocr_summary or "[sin datos]")
    print("OCR ERRORES:",len(ocr_errors))
    for r in ocr_errors:
        print(" ",r)
    print("OCR PENDIENTES/PROCESANDO:",len(ocr_pending))
    for r in ocr_pending:
        print(" ",r)
    print()

    phase=str(state.get("phase","") or "")
    last_error=str(state.get("last_error","") or "")
    print("DIAGNOSTICO")
    print("  phase:",phase or "[vacio]")
    print("  last_error:",last_error or "[vacio]")
    print("  current_file:",state.get("current_file","") or "[vacio]")
    print("  pending_changes:",bool(state.get("pending_changes",False)))
    print()

    if phase=="error" and last_error and not extraction and not ocr_errors:
        print("CONCLUSION PROBABLE:")
        print("  AutoSync SI tiene un error real persistido en last_error.")
        print("  La pestaña 'Errores y pendientes' no lo muestra porque lista")
        print("  errores de extraccion y OCR, no AutoSync.last_error.")
    elif phase=="error" and not last_error:
        print("CONCLUSION PROBABLE:")
        print("  Estado residual: phase=error pero last_error esta vacio.")
    elif phase!="error":
        print("CONCLUSION PROBABLE:")
        print("  El estado persistido no esta en error.")
    else:
        print("CONCLUSION: revisar detalles anteriores.")

    print()
    print("VERIFICACION: SOLO LECTURA. No se modifico nada.")

if __name__=="__main__":
    main()
