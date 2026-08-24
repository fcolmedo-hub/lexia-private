from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True, slots=True)
class KnowledgeDocument:
    """Metadatos jurídicos locales derivados de un documento del catálogo."""

    path: str
    content_hash: str
    name: str
    category: str
    concepts: tuple[str, ...]
    cited_rules: tuple[str, ...]
    authorities: tuple[str, ...]
    jurisdictions: tuple[str, ...]


class DeterministicKnowledgeExtractor:
    """Extrae señales jurídicas mediante reglas reproducibles, sin servicios externos."""

    CONCEPT_RULES = (
        ("Acto administrativo", ("acto administrativo", "nulidad del acto")),
        ("Motivación", ("motivacion", "fundamentacion")),
        ("Competencia administrativa", ("competencia administrativa",)),
        ("Responsabilidad del Estado", ("responsabilidad del estado", "responsabilidad estatal", "falta de servicio")),
        ("Mutuales", ("asociacion mutual", "mutual")),
        ("Ingresos brutos", ("ingresos brutos", "iibb")),
        ("Medida cautelar", ("medida cautelar", "verosimilitud del derecho", "peligro en la demora")),
        ("Prescripción", ("prescripcion", "caducidad")),
        ("Daños y perjuicios", ("danos y perjuicios", "indemnizacion", "lucro cesante", "dano emergente")),
        ("Derecho de defensa", ("derecho de defensa", "debido proceso")),
        ("Recurso", ("recurso extraordinario", "apelacion", "casacion", "queja")),
        ("Prueba", ("prueba documental", "prueba pericial", "carga de la prueba")),
    )
    AUTHORITY_RULES = (
        ("CSJN", ("corte suprema de justicia de la nacion", "csjn")),
        ("Corte IDH", ("corte interamericana", "corte idh", "cidh")),
        ("Casación", ("camara de casacion", "casacion penal", "cfcp")),
        ("Cámara", ("camara nacional", "camara federal")),
        ("Superior Tribunal", ("superior tribunal", "suprema corte provincial", "corte de justicia")),
        ("Tribunal Fiscal", ("tribunal fiscal",)),
    )
    JURISDICTION_RULES = (
        ("Nacional/Federal", ("nacional", "federal", "csjn")),
        ("Entre Ríos", ("entre rios", "parana", "ater")),
        ("Santa Fe", ("santa fe", "rosario")),
        ("Córdoba", ("cordoba", "villa maria")),
        ("Buenos Aires", ("buenos aires", "la plata")),
        ("Mendoza", ("mendoza",)),
        ("Municipal", ("municipalidad", "municipio")),
    )
    RULE_PATTERN = re.compile(
        r"\b(?:ley|decreto|resolucion|ordenanza|codigo|art(?:iculo)?\.?)\s+(?:n[.°º]?\s*)?[\d.\-/]+",
        re.IGNORECASE,
    )

    def extract(self, path, content_hash, name, category, text) -> KnowledgeDocument:
        normalized = self._normalize(" ".join((str(name or ""), str(text or ""))))
        return KnowledgeDocument(
            path=str(path),
            content_hash=str(content_hash or ""),
            name=str(name or ""),
            category=str(category or "Sin categoría"),
            concepts=self._matches(normalized, self.CONCEPT_RULES),
            cited_rules=self._rules(str(text or "")),
            authorities=self._matches(normalized, self.AUTHORITY_RULES),
            jurisdictions=self._matches(normalized, self.JURISDICTION_RULES),
        )

    @staticmethod
    def _normalize(value: str) -> str:
        folded = unicodedata.normalize("NFKD", str(value or ""))
        return "".join(char for char in folded if not unicodedata.combining(char)).casefold()

    @staticmethod
    def _unique(values: Iterable[str]) -> tuple[str, ...]:
        return tuple(dict.fromkeys(value for value in values if value))

    def _matches(self, text: str, rules) -> tuple[str, ...]:
        return self._unique(label for label, terms in rules if any(term in text for term in terms))

    def _rules(self, text: str) -> tuple[str, ...]:
        return self._unique(match.group(0).strip() for match in self.RULE_PATTERN.finditer(text))
