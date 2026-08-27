from __future__ import annotations

import re
import sqlite3
from pathlib import Path

MONTHS = {
    "enero": "01", "febrero": "02", "marzo": "03", "abril": "04",
    "mayo": "05", "junio": "06", "julio": "07", "agosto": "08",
    "septiembre": "09", "setiembre": "09", "octubre": "10",
    "noviembre": "11", "diciembre": "12",
}


def clean(s):
    return re.sub(r"\s+", " ", str(s or "")).strip(" -–—\t\r\n")


def lines(text, limit=220):
    out = []
    for raw in str(text or "").splitlines():
        s = clean(raw)
        if not s or s.startswith("--- PÁGINA"):
            continue
        out.append(s)
        if len(out) >= limit:
            break
    return out


def _looks_like_sentence(s):
    s = clean(s)
    if len(s) > 150:
        return True
    low = s.casefold()
    bad = (
        "dispuso ", "rechazar ", "interpuesto ", "transferir ", "se transfiera",
        "contra la resolución", "instancia anterior", "se agravia", "considerando",
        "resulta que", "por la cual", "a favor de", "recurso de apelación",
        "iniciaron una demanda", "interpone la actora", "deduce demanda",
        "mantener la vigencia", "se presentó", "promovió demanda",
    )
    return any(token in low for token in bad)


def _looks_like_header(s):
    s = clean(s)
    if not s or len(s) > 170:
        return False
    low = s.casefold()
    if re.match(r"^\d+[º°.)-]", s):
        return False
    if _looks_like_sentence(s):
        return False
    strong = (
        "juzgado:", "tribunal:", "cámara:", "camara:",
        "corte suprema", "camara federal", "cámara federal",
        "camara civil", "cámara civil", "tribunal oral", "juzgado federal",
    )
    return any(token in low for token in strong) or s.isupper()


def find_court(ls):
    exact = (
        r"^(CORTE SUPREMA DE JUSTICIA DE LA NACI[ÓO]N)$",
        r"^(CORTE SUPREMA DE JUSTICIA DE [A-ZÁÉÍÓÚÑ ]{3,80})$",
        r"^(C[ÁA]MARA(?: NACIONAL| FEDERAL| DE APELACI[ÓO]N)? [A-ZÁÉÍÓÚÑ0-9 .°º()-]{3,100})$",
        r"^(TRIBUNAL ORAL(?: EN LO [A-ZÁÉÍÓÚÑ ]+)?(?: FEDERAL)?(?: N[°º.]? ?\d+)?)$",
        r"^(JUZGADO(?: NACIONAL)?(?: FEDERAL)?(?: DE 1RA INSTANCIA)?(?: EN LO [A-ZÁÉÍÓÚÑ ]+)?(?: DE [A-ZÁÉÍÓÚÑ ]+)?(?: N[°º.]? ?\d+| ?\d+)?)$",
    )
    prefixed = re.compile(r"^(?:JUZGADO|TRIBUNAL|C[ÁA]MARA|CORTE)\b", re.I)

    for s in ls[:120]:
        u = clean(s.upper())
        if not prefixed.match(u) or _looks_like_sentence(s):
            continue
        for pat in exact:
            m = re.match(pat, u, re.I)
            if m:
                value = clean(m.group(1)).rstrip("),.;:")
                if 8 <= len(value) <= 140:
                    return value, s

    # Structured metadata lines exported by legal databases.
    for s in ls[:150]:
        m = re.match(r"^(?:Juzgado|Tribunal|C[áa]mara)\s*:\s*(.{8,150})$", s, re.I)
        if not m:
            continue
        value = clean(m.group(1)).rstrip(".;:")
        if re.search(r"\b(?:juzgado|tribunal|c[áa]mara|corte)\b", value, re.I):
            return value.upper(), s
    return "", ""


def find_chamber(ls):
    # A Sala is reliable only when it belongs to a header/metadata line.
    # This intentionally rejects citations such as "4º) La Sala B..." or
    # "CNAT Sala X" embedded in the reasoning of another court.
    for s in ls[:160]:
        if not _looks_like_header(s):
            continue
        m = re.search(r"\bSALA\s+(?:N[°º.]?\s*)?([IVXLC]+|[A-Z]|\d+)\b", s, re.I)
        if m:
            return f"Sala {m.group(1)}", s
    return "", ""


def find_date(ls):
    priority = []
    for s in ls[:180]:
        low = s.casefold()
        explicit = any(token in low for token in (
            "fecha de firma", "fecha del fallo", "fecha de sentencia",
            "sentencia de fecha", "dictada el", "firmado el",
        ))
        dateline = len(s) <= 90 and bool(re.match(
            r"^[A-ZÁÉÍÓÚÑa-záéíóúñ ]{2,35},\s*\d{1,2}\s+de\s+",
            s,
        ))
        if explicit or dateline:
            priority.append(s)

    for s in priority:
        m = re.search(r"\b(\d{1,2})[/-](\d{1,2})[/-](\d{2,4})\b", s)
        if m:
            d, mo, y = m.groups()
            y = int(y)
            y = y + 2000 if y < 50 else y + 1900 if y < 100 else y
            if 1 <= int(d) <= 31 and 1 <= int(mo) <= 12 and 1900 <= y <= 2100:
                return f"{y:04d}-{int(mo):02d}-{int(d):02d}", s

        m = re.search(
            r"\b(\d{1,2})\s+de\s+(enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|setiembre|octubre|noviembre|diciembre)\s+de\s+(\d{4})\b",
            s,
            re.I,
        )
        if m:
            return (
                f"{int(m.group(3)):04d}-{int(MONTHS[m.group(2).casefold()]):02d}-{int(m.group(1)):02d}",
                s,
            )
    return "", ""


def find_case_number(ls):
    patterns = (
        r"\b(?:EXPTE\.?|EXPEDIENTE)\s*(?:N[°º.]?\s*)?[:.-]?\s*([A-Z]{0,8}\s*\d[0-9A-Z_./-]{1,35})",
        r"\bCAUSA\s*(?:N[°º.]?\s*)?[:.-]?\s*([A-Z]{0,8}\s*\d[0-9A-Z_./-]{1,35})",
    )
    for s in ls[:180]:
        for pat in patterns:
            m = re.search(pat, s, re.I)
            if not m:
                continue
            value = clean(m.group(1)).rstrip(".,;:)")
            if not re.search(r"\d", value):
                continue
            if 2 <= len(value) <= 45:
                return value, s
    return "", ""


def _trim_title(value):
    value = clean(value)
    value = re.split(
        r"\s+(?:expediente|expte\.?|causa)\s*(?:n[°º.]?)?\b",
        value,
        maxsplit=1,
        flags=re.I,
    )[0]
    return value.strip(' “"”.,;:-')


def _valid_title(value):
    value = _trim_title(value)
    if not 8 <= len(value) <= 220:
        return False
    if _looks_like_sentence(value):
        return False
    # A real carátula normally contains an adversarial/proceeding marker.
    return bool(re.search(r"\b(c/|contra|s/)\b", value, re.I))


def find_title(ls):
    # Explicit metadata is strongest.
    for s in ls[:180]:
        m = re.search(r"\b(?:CAR[ÁA]TULA|AUTOS)\s*[:.-]\s*(.{8,220})", s, re.I)
        if m:
            value = _trim_title(m.group(1))
            if _valid_title(value):
                return value, s

    # Formula commonly used by provincial judgments.
    for s in ls[:160]:
        m = re.search(r"\bVISTO\s*:\s*Estos caratulados\s*[“\"]?(.{8,220})", s, re.I)
        if m:
            value = _trim_title(m.group(1))
            if _valid_title(value):
                return value, s

    # Quoted case names. Do not accept unquoted narrative prose as a fallback.
    for s in ls[:150]:
        quoted = re.findall(r"[“\"]([^”\"]{8,220})[”\"]", s)
        for candidate in quoted:
            value = _trim_title(candidate)
            if _valid_title(value):
                return value, s

    return "", ""


def extract(text):
    ls = lines(text)
    court, ce = find_court(ls)
    chamber, se = find_chamber(ls)
    date, de = find_date(ls)
    number, ne = find_case_number(ls)
    title, te = find_title(ls)

    confidence = {
        "court": 1.0 if court else 0.0,
        "chamber": 0.95 if chamber else 0.0,
        "date": 0.95 if date else 0.0,
        "case_title": 0.95 if title else 0.0,
        "case_number": 0.95 if number else 0.0,
    }

    return {
        "court": court,
        "chamber": chamber,
        "date": date,
        "case_title": title,
        "case_number": number,
        "confidence": confidence,
        "evidence": {
            "court": ce,
            "chamber": se,
            "date": de,
            "case_title": te,
            "case_number": ne,
        },
    }


def sample_from_catalog(database_path, limit=10):
    con = sqlite3.connect(Path(database_path))
    con.row_factory = sqlite3.Row
    try:
        rows = con.execute(
            """
            SELECT
                d.path,
                d.name,
                d.text_content,
                COALESCE(j.hierarchy_group,'') hierarchy_group,
                COALESCE(j.scope,'') scope,
                COALESCE(j.province,'') province
            FROM documents d
            LEFT JOIN jurisprudence_index j ON j.document_path=d.path
            WHERE COALESCE(d.is_deleted,0)=0
              AND d.category='Jurisprudencia'
              AND LENGTH(COALESCE(d.text_content,''))>500
            ORDER BY j.hierarchy_group,d.name
            """
        ).fetchall()

        groups = {}
        for r in rows:
            groups.setdefault(r["hierarchy_group"] or "Sin grupo", []).append(r)

        selected = []
        while len(selected) < limit:
            progressed = False
            for key in sorted(groups):
                if groups[key]:
                    selected.append(groups[key].pop(0))
                    progressed = True
                if len(selected) >= limit:
                    break
            if not progressed:
                break

        out = []
        for r in selected:
            item = {
                "document_name": r["name"],
                "document_path": r["path"],
                "hierarchy_group": r["hierarchy_group"],
                "scope": r["scope"],
                "province": r["province"],
                "text_length": len(r["text_content"] or ""),
            }
            item.update(extract(r["text_content"] or ""))
            out.append(item)
        return out
    finally:
        con.close()
