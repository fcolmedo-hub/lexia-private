from __future__ import annotations

import re
import sqlite3
from pathlib import Path

MONTHS={"enero":"01","febrero":"02","marzo":"03","abril":"04","mayo":"05","junio":"06","julio":"07","agosto":"08","septiembre":"09","setiembre":"09","octubre":"10","noviembre":"11","diciembre":"12"}

def clean(s):
    return re.sub(r"\s+"," ",str(s or "")).strip(" -–—\t\r\n")

def lines(text,limit=180):
    out=[]
    for raw in str(text or "").splitlines():
        s=clean(raw)
        if not s or s.startswith("--- PÁGINA"): continue
        out.append(s)
        if len(out)>=limit: break
    return out

def find_court(ls):
    pats=(r"^(CORTE SUPREMA DE JUSTICIA DE LA NACI[ÓO]N)\b",r"^(CORTE SUPREMA DE JUSTICIA DE [A-ZÁÉÍÓÚÑ ]+)\b",r"^(C[ÁA]MARA [^\n]{0,120})$",r"^(TRIBUNAL ORAL [^\n]{0,120})$",r"^(JUZGADO [^\n]{0,120})$")
    for s in ls[:100]:
        u=s.upper()
        for p in pats:
            m=re.match(p,u,re.I)
            if m and 8<=len(clean(m.group(1)))<=150: return clean(m.group(1)),s
    return "",""

def find_chamber(ls):
    for s in ls[:120]:
        m=re.search(r"\bSALA\s+(?:N[°º.]?\s*)?([IVXLC]+|\d+)\b",s,re.I)
        if m: return f"Sala {m.group(1)}",s
    return "",""

def find_date(ls):
    for s in ls[:140]:
        m=re.search(r"\b(\d{1,2})[/-](\d{1,2})[/-](\d{2,4})\b",s)
        if m:
            d,mo,y=m.groups(); y=int(y); y=y+2000 if y<50 else y+1900 if y<100 else y
            if 1<=int(d)<=31 and 1<=int(mo)<=12 and 1900<=y<=2100: return f"{y:04d}-{int(mo):02d}-{int(d):02d}",s
        m=re.search(r"\b(\d{1,2})\s+de\s+(enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|setiembre|octubre|noviembre|diciembre)\s+de\s+(\d{4})\b",s,re.I)
        if m: return f"{int(m.group(3)):04d}-{int(MONTHS[m.group(2).casefold()]):02d}-{int(m.group(1)):02d}",s
    return "",""

def find_case_number(ls):
    for s in ls[:160]:
        m=re.search(r"\b(?:EXPTE\.?|EXPEDIENTE|CAUSA)\s*(?:N[°º.]?\s*)?[:.-]?\s*([A-Z0-9][A-Z0-9_./-]{2,40})",s,re.I)
        if m: return clean(m.group(1)),s
    return "",""

def find_title(ls):
    for s in ls[:160]:
        m=re.search(r"\b(?:AUTOS|CAR[ÁA]TULA)\s*[:.-]\s*(.{8,180})",s,re.I)
        if m: return clean(m.group(1)),s
    for s in ls[:100]:
        if len(s)<=180 and re.search(r"\b(c/|contra|s/)\b",s,re.I) and not s.casefold().startswith(("visto","considerando","que ")): return s,s
    return "",""

def extract(text):
    ls=lines(text)
    court,ce=find_court(ls); chamber,se=find_chamber(ls); date,de=find_date(ls); number,ne=find_case_number(ls); title,te=find_title(ls)
    return {"court":court,"chamber":chamber,"date":date,"case_title":title,"case_number":number,"evidence":{"court":ce,"chamber":se,"date":de,"case_title":te,"case_number":ne}}

def sample_from_catalog(database_path,limit=10):
    con=sqlite3.connect(Path(database_path)); con.row_factory=sqlite3.Row
    try:
        rows=con.execute("""SELECT d.path,d.name,d.text_content,COALESCE(j.hierarchy_group,'') hierarchy_group,COALESCE(j.scope,'') scope,COALESCE(j.province,'') province FROM documents d LEFT JOIN jurisprudence_index j ON j.document_path=d.path WHERE COALESCE(d.is_deleted,0)=0 AND d.category='Jurisprudencia' AND LENGTH(COALESCE(d.text_content,''))>500 ORDER BY j.hierarchy_group,d.name""").fetchall()
        groups={}
        for r in rows: groups.setdefault(r['hierarchy_group'] or 'Sin grupo',[]).append(r)
        selected=[]
        while len(selected)<limit:
            progressed=False
            for key in sorted(groups):
                if groups[key]: selected.append(groups[key].pop(0)); progressed=True
                if len(selected)>=limit: break
            if not progressed: break
        out=[]
        for r in selected:
            item={"document_name":r['name'],"document_path":r['path'],"hierarchy_group":r['hierarchy_group'],"scope":r['scope'],"province":r['province'],"text_length":len(r['text_content'] or '')}
            item.update(extract(r['text_content'] or '')); out.append(item)
        return out
    finally: con.close()
