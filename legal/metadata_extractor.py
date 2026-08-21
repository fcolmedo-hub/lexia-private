import re
from pathlib import Path

from config.settings import SETTINGS


class LegalMetadataExtractor:
    COURT_PATTERNS = (
        r"Corte Suprema de Justicia de la Nación",
        r"CSJN",
        r"Corte Interamericana de Derechos Humanos",
        r"Cámara Federal de Casación Penal",
        r"Cámara Federal de [^\n,.;]+",
        r"Cámara Nacional de [^\n,.;]+",
        r"Suprema Corte de Justicia de [^\n,.;]+",
        r"Superior Tribunal de Justicia de [^\n,.;]+",
        r"Tribunal Fiscal de la Nación",
        r"Juzgado [^\n,.;]+",
    )

    DATE_PATTERNS = (
        r"\b\d{1,2}/\d{1,2}/\d{4}\b",
        r"\b\d{1,2}\s+de\s+[a-záéíóú]+\s+de\s+\d{4}\b",
    )

    EXPEDIENT_PATTERNS = (
        r"\bExpte\.?\s*(?:N[.°º]?\s*)?[A-Za-z0-9\-\/\.]+",
        r"\bExpediente\s*(?:N[.°º]?\s*)?[A-Za-z0-9\-\/\.]+",
        r"\bCausa\s*(?:N[.°º]?\s*)?[A-Za-z0-9\-\/\.]+",
    )

    LAW_PATTERN = re.compile(
        r"\b(?:Ley|Decreto|Resolución|Ordenanza|Código)\s+"
        r"(?:N[.°º]?\s*)?[\d\.\-\/]+",
        flags=re.IGNORECASE,
    )

    ARTICLE_PATTERN = re.compile(
        r"\b(?:art(?:ículo)?\.?\s*)\d+(?:\s*(?:bis|ter))?"
        r"(?:\s*(?:inc(?:iso)?\.?\s*)[a-z0-9°º]+)?",
        flags=re.IGNORECASE,
    )

    FALLLOS_PATTERN = re.compile(
        r"\bFallos\s+\d{2,4}:\d{1,5}\b",
        flags=re.IGNORECASE,
    )

    MATTER_RULES: dict[str, tuple[str, ...]] = {
        "Tributario": (
            "impuesto",
            "tributario",
            "fiscal",
            "ingresos brutos",
            "iva",
            "ganancias",
            "solve et repete",
            "coparticipación",
        ),
        "Administrativo": (
            "acto administrativo",
            "procedimiento administrativo",
            "responsabilidad del estado",
            "administración pública",
            "amparo por mora",
        ),
        "Penal económico": (
            "evasión",
            "penal tributaria",
            "lavado",
            "contrabando",
            "acción penal",
            "imputado",
        ),
        "Civil y comercial": (
            "contrato",
            "daños y perjuicios",
            "responsabilidad civil",
            "sociedad",
            "consumidor",
        ),
        "Constitucional": (
            "inconstitucionalidad",
            "constitución nacional",
            "arbitrariedad",
            "caso federal",
            "garantía constitucional",
        ),
    }

    JURISDICTION_RULES: dict[str, tuple[str, ...]] = {
        "Nacional/Federal": (
            "corte suprema de justicia de la nación",
            "cámara federal",
            "juzgado federal",
            "constitución nacional",
        ),
        "Santa Fe": ("santa fe", "rosario"),
        "Entre Ríos": ("entre ríos", "paraná"),
        "Córdoba": ("córdoba", "villa maría"),
        "Buenos Aires": ("provincia de buenos aires", "la plata"),
        "Mendoza": ("mendoza",),
    }

    def extract(
        self,
        text: str,
        path: str | Path,
        category: str,
    ) -> dict[str, str]:
        head = text[: SETTINGS.metadata_preview_chars]
        metadata: dict[str, str] = {
            "category": category,
            "filename": Path(path).name,
        }

        metadata["title"] = self._title(head, path)

        court = self._first_match(head, self.COURT_PATTERNS)
        if court:
            metadata["court"] = court

        date = self._first_match(head, self.DATE_PATTERNS)
        if date:
            metadata["date"] = date

        expediente = self._first_match(head, self.EXPEDIENT_PATTERNS)
        if expediente:
            metadata["expedient"] = expediente

        laws = sorted(set(self.LAW_PATTERN.findall(head)))
        if laws:
            metadata["laws"] = " | ".join(laws[:30])

        articles = sorted(set(self.ARTICLE_PATTERN.findall(head)))
        if articles:
            metadata["articles"] = " | ".join(articles[:40])

        fallos = sorted(set(self.FALLLOS_PATTERN.findall(head)))
        if fallos:
            metadata["fallos_citations"] = " | ".join(fallos[:20])

        metadata["document_kind"] = self._infer_kind(head, category)

        matter = self._infer_rule(head, self.MATTER_RULES)
        if matter:
            metadata["matter"] = matter

        jurisdiction = self._infer_rule(
            head,
            self.JURISDICTION_RULES,
        )
        if jurisdiction:
            metadata["jurisdiction"] = jurisdiction

        metadata["year"] = self._infer_year(
            metadata.get("date", "")
        )

        return metadata

    def _first_match(
        self,
        text: str,
        patterns: tuple[str, ...],
    ) -> str | None:
        for pattern in patterns:
            match = re.search(
                pattern,
                text,
                flags=re.IGNORECASE,
            )
            if match:
                return match.group(0).strip()
        return None

    def _title(self, text: str, path: str | Path) -> str:
        lines = [
            line.strip()
            for line in text.splitlines()
            if line.strip()
            and not line.startswith("--- PÁGINA")
        ]

        for line in lines[:15]:
            if 8 <= len(line) <= 220:
                return line

        return Path(path).stem

    def _infer_kind(self, text: str, category: str) -> str:
        lower = text.lower()
        category_lower = category.lower()

        if category_lower == "jurisprudencia":
            return "Fallo judicial"
        if category_lower == "doctrina":
            return "Doctrina"
        if category_lower in {"leyes", "legislación"}:
            return "Normativa"
        if "petitorio" in lower and "hechos" in lower:
            return "Escrito judicial"
        if "resuelve" in lower or "sentencia" in lower:
            return "Fallo judicial"

        return category or "Documento jurídico"

    def _infer_rule(
        self,
        text: str,
        rules: dict[str, tuple[str, ...]],
    ) -> str | None:
        lower = text.lower()
        best_name = None
        best_hits = 0

        for name, terms in rules.items():
            hits = sum(
                1
                for term in terms
                if term in lower
            )

            if hits > best_hits:
                best_name = name
                best_hits = hits

        return best_name if best_hits else None

    def _infer_year(self, date: str) -> str:
        match = re.search(r"\b(19|20)\d{2}\b", date)
        return match.group(0) if match else ""
