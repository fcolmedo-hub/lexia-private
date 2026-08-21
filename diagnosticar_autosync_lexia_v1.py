#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""LexIA - Diagnostico Auto-Sync v1.0. SOLO LECTURA."""
import argparse, hashlib, sqlite3
from pathlib import Path

def sha256(p):
    h=hashlib.sha256()
    with p.open("rb") as f:
        for b in iter(lambda:f.read(1048576), b""): h.update(b)
    return h.hexdigest()

def main():
    a=argparse.ArgumentParser()
    a.add_argument("root"); a.add_argument("file")
    x=a.parse_args()
    root=Path(x.root).resolve(); target=Path(x.file).resolve()
    db=root/"runtime"/"lexia_catalog.sqlite3"
    print("# LEXIA - DIAGNOSTICO AUTO-SYNC v1.0 (SOLO LECTURA)")
    print("Archivo:",target)
    print("Existe:",target.exists())
    if target.exists():
        s=target.stat()
        print("Tamano fisico:",s.st_size)
        print("mtime_ns:",s.st_mtime_ns)
        print("SHA256 fisico:",sha256(target))
    if not db.exists(): raise SystemExit("No existe catalogo: "+str(db))
    con=sqlite3.connect(db.resolve().as_uri()+"?mode=ro",uri=True); con.row_factory=sqlite3.Row
    con.execute("PRAGMA query_only=ON")
    tabs={r[0] for r in con.execute("select name from sqlite_master where type in ('table','view')")}
    def cols(t): return [r["name"] for r in con.execute("pragma table_info("+t+")")]
    def pick(cs, opts):
        d={c.lower():c for c in cs}
        return next((d[o] for o in opts if o in d),None)
    for t in ("documents","document_locations"):
        if t not in tabs: continue
        cs=cols(t); pc=pick(cs,["document_path","path","file_path","source_path","location"])
        nc=pick(cs,["document_name","name","filename","file_name"])
        print("\n"+t.upper()); print("columnas:",", ".join(cs))
        wh=[]; pa=[]
        if pc: wh.append(pc+"=?"); pa.append(str(target))
        if nc: wh.append(nc+"=?"); pa.append(target.name)
        if not wh: print("[sin columnas de ruta/nombre detectables]"); continue
        rows=list(con.execute("select * from "+t+" where "+" OR ".join(wh)+" limit 10",pa))
        print("coincidencias:",len(rows))
        for i,r in enumerate(rows,1):
            vals=[]
            for k in r.keys():
                v="" if r[k] is None else str(r[k])
                if len(v)>160:v=v[:157]+"..."
                vals.append(k+"="+v)
            print(str(i)+". "+" | ".join(vals))
    for t in ("fragments","fragments_fts"):
        if t not in tabs: continue
        cs=cols(t); pc=pick(cs,["document_path","path","file_path","source_path"])
        print("\n"+t.upper())
        if pc:
            try: print("filas ruta exacta:",con.execute("select count(*) from "+t+" where "+pc+"=?",(str(target),)).fetchone()[0])
            except Exception as e: print("no pudo contarse:",e)
        else: print("[sin columna de ruta]")
    print("\nINSTRUCCION")
    print("1) Ejecutar ahora y conservar salida ANTES.")
    print("2) Modificar una frase distintiva del documento sin cambiar nombre ni ruta.")
    print("3) Guardar y esperar el ciclo de Auto-Sync.")
    print("4) Ejecutar nuevamente y conservar salida DESPUES.")
    print("\nVERIFICACION: no se modifico catalogo, FTS, Qdrant, Knowledge ni archivo.")
    con.close()
if __name__=="__main__": main()
