import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path


@dataclass(slots=True)
class Classification:
    document_type: str
    subtype: str
    confidence: float
    reasons: list[str]
    detected_authority: str = ""
    detected_jurisdiction: str = ""


class DeterministicDocumentClassifier:
    """
    Clasificador jurídico determinista.

    No usa IA ni servicios externos. Aplica señales ponderadas sobre:
    - encabezados y fórmulas características;
    - vocabulario procesal;
    - estructura del documento;
    - organismos, tribunales y referencias normativas.

    La carpeta física no participa de la decisión.
    """

    TYPES = {
        "Jurisprudencia": (
            (7, r"\b(?:sentencia|fallo)\b"),
            (7, r"\b(?:resuelve|fallamos|acuerda)\s*:"),
            (6, r"\b(?:corte suprema|superior tribunal|c[aá]mara .* apel)"),
            (5, r"\b(?:voto del|considerando que|por ello,? el tribunal)"),
            (5, r"\bautos caratulados\b"),
            (4, r"\b(?:juez|jueces|magistrados)\b"),
            (4, r"\bfallos\s*:?\s*\d{2,4}:\d+"),
        ),
        "Legislación": (
            (8, r"^\s*(?:ley|decreto|ordenanza|resoluci[oó]n)\s+(?:n[º°o.]?\s*)?\d+"),
            (7, r"\b(?:el senado y c[aá]mara de diputados|legislatura)\b"),
            (6, r"\bprom[uú]lgase\b"),
            (5, r"\bbolet[ií]n oficial\b"),
            (4, r"\bart[ií]culo\s+\d+[º°]?\s*[-.—:]"),
            (4, r"\btexto ordenado\b"),
        ),
        "Escritos": (
            (8, r"\b(?:señor juez|señora jueza|excelent[ií]sima c[aá]mara)\b"),
            (7, r"\b(?:vengo a|venimos a)\s+(?:interponer|promover|contestar|solicitar)"),
            (6, r"\b(?:objeto|petitorio|personer[ií]a|constituyo domicilio)\b"),
            (5, r"\b(?:mi defendido|mi representada|esta parte)\b"),
            (5, r"\b(?:demanda|contestaci[oó]n|recurso de apelaci[oó]n|recurso extraordinario)\b"),
            (4, r"\bproveer de conformidad\b"),
        ),
        "Doctrina": (
            (7, r"\b(?:resumen|abstract|palabras clave|keywords)\b"),
            (6, r"\b(?:autor|profesor|doctor en derecho|universidad)\b"),
            (5, r"\b(?:bibliograf[ií]a|referencias bibliogr[aá]ficas)\b"),
            (5, r"\b(?:revista jur[ií]dica|editorial|isbn|issn)\b"),
            (4, r"\b(?:cap[ií]tulo|introducci[oó]n|conclusiones)\b"),
            (3, r"\b(?:doctrina|autor citado|op\. cit\.)\b"),
        ),
        "Dictámenes": (
            (8, r"\bdictamen\b"),
            (7, r"\b(?:procuraci[oó]n|fiscal[ií]a de estado|asesor[ií]a letrada)\b"),
            (6, r"\b(?:señor ministro|señor procurador|a vuestra excelencia)\b"),
            (5, r"\bopino que\b"),
        ),
        "Contratos": (
            (8, r"\b(?:contrato|convenio)\s+de\b"),
            (7, r"\bentre .* y .*,? se conviene\b"),
            (6, r"\b(?:cl[aá]usula|primera:|segunda:|las partes)\b"),
            (5, r"\b(?:vigencia|rescisi[oó]n|precio|obligaciones)\b"),
        ),
        "Informes y pericias": (
            (8, r"\b(?:informe pericial|pericia|dictamen pericial)\b"),
            (6, r"\b(?:metodolog[ií]a|conclusiones t[eé]cnicas|puntos de pericia)\b"),
            (5, r"\b(?:perito|experto|laboratorio)\b"),
        ),
        "Expedientes administrativos": (
            (7, r"\bexpediente administrativo\b"),
            (6, r"\b(?:actuaciones administrativas|tr[aá]mite administrativo)\b"),
            (5, r"\b(?:providencia|pase a|g[ií]rese|notif[ií]quese)\b"),
        ),
    }

    SUBTYPES = (
        ("Recurso extraordinario", r"\brecurso extraordinario\b"),
        ("Recurso de apelación", r"\brecurso de apelaci[oó]n\b"),
        ("Recurso de queja", r"\brecurso de queja\b"),
        ("Demanda", r"\b(?:promueve|interpone)\s+demanda\b"),
        ("Contestación de demanda", r"\bcontesta(?:ci[oó]n de)?\s+demanda\b"),
        ("Medida cautelar", r"\bmedida cautelar\b"),
        ("Sentencia definitiva", r"\bsentencia definitiva\b"),
        ("Sentencia interlocutoria", r"\bsentencia interlocutoria\b"),
        ("Resolución administrativa", r"\bresoluci[oó]n\s+(?:n[º°o.]?\s*)?\d+"),
        ("Ley", r"^\s*ley\s+(?:n[º°o.]?\s*)?\d+"),
        ("Decreto", r"^\s*decreto\s+(?:n[º°o.]?\s*)?\d+"),
        ("Ordenanza", r"^\s*ordenanza\s+(?:n[º°o.]?\s*)?\d+"),
        ("Artículo doctrinario", r"\b(?:abstract|palabras clave|issn)\b"),
        ("Contrato de agencia", r"\bcontrato de agencia\b"),
        ("Informe pericial", r"\b(?:informe pericial|puntos de pericia)\b"),
    )

    AUTHORITIES = (
        ("Corte Suprema de Justicia de la Nación",
         ("corte suprema de justicia de la nación", "csjn")),
        ("Superior Tribunal de Justicia",
         ("superior tribunal de justicia", "stj")),
        ("Suprema Corte de Justicia",
         ("suprema corte de justicia",)),
        ("Cámara Federal",
         ("cámara federal", "camara federal")),
        ("Cámara de Apelaciones",
         ("cámara de apelaciones", "camara de apelaciones")),
        ("Tribunal Fiscal",
         ("tribunal fiscal",)),
        ("Juzgado Federal",
         ("juzgado federal",)),
    )

    JURISDICTIONS = (
        ("Nacional/Federal", ("nación", "nacion", "federal", "csjn")),
        ("Santa Fe", ("santa fe", "rosario", "pérez", "perez")),
        ("Entre Ríos", ("entre ríos", "entre rios", "paraná", "parana", "ater")),
        ("Córdoba", ("córdoba", "cordoba", "villa maría", "villa maria")),
        ("Buenos Aires", ("buenos aires", "la plata")),
        ("Mendoza", ("mendoza",)),
    )

    def classify(
        self,
        text: str,
        file_path: str | Path,
    ) -> Classification:
        sample = self._normalize(
            f"{Path(file_path).name}\n{text[:100000]}"
        )

        scores: dict[str, int] = {}
        reasons: dict[str, list[str]] = {}

        for document_type, rules in self.TYPES.items():
            total = 0
            matched = []

            for weight, pattern in rules:
                if re.search(
                    pattern,
                    sample,
                    flags=re.IGNORECASE | re.MULTILINE,
                ):
                    total += weight
                    matched.append(
                        self._reason_from_pattern(pattern)
                    )

            scores[document_type] = total
            reasons[document_type] = matched

        best_type = max(
            scores,
            key=scores.get,
        )
        best_score = scores[best_type]
        ordered_scores = sorted(
            scores.values(),
            reverse=True,
        )
        second_score = (
            ordered_scores[1]
            if len(ordered_scores) > 1
            else 0
        )

        if best_score < 6:
            best_type = "Otros"
            confidence = 0.35
            selected_reasons = [
                "No se detectaron señales suficientes"
            ]
        else:
            margin = max(0, best_score - second_score)
            confidence = min(
                0.99,
                0.52
                + best_score * 0.025
                + margin * 0.02,
            )
            selected_reasons = reasons[best_type][:6]

        subtype = self._first_regex(
            sample,
            self.SUBTYPES,
        )
        authority = self._first_alias(
            sample,
            self.AUTHORITIES,
        )
        jurisdiction = self._first_alias(
            sample,
            self.JURISDICTIONS,
        )

        return Classification(
            document_type=best_type,
            subtype=subtype,
            confidence=round(confidence, 2),
            reasons=selected_reasons,
            detected_authority=authority,
            detected_jurisdiction=jurisdiction,
        )

    def _first_regex(self, text: str, rules) -> str:
        for label, pattern in rules:
            if re.search(
                pattern,
                text,
                flags=re.IGNORECASE | re.MULTILINE,
            ):
                return label
        return ""

    def _first_alias(self, text: str, rules) -> str:
        for label, aliases in rules:
            if any(
                self._normalize(alias) in text
                for alias in aliases
            ):
                return label
        return ""

    def _reason_from_pattern(self, pattern: str) -> str:
        clean = re.sub(r"\\[bBsSwW]", "", pattern)
        clean = re.sub(r"[\^\$\(\)\[\]\?\+\*\|]", " ", clean)
        clean = clean.replace("\\s", " ").replace("\\", "")
        return " ".join(clean.split())[:100]

    def _normalize(self, text: str) -> str:
        decomposed = unicodedata.normalize(
            "NFKD",
            text.lower(),
        )
        without_marks = "".join(
            char
            for char in decomposed
            if not unicodedata.combining(char)
        )
        return re.sub(r"\s+", " ", without_marks)
