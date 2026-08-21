import re
from collections import OrderedDict

from config.settings import SETTINGS
from models.query_interpretation import QueryInterpretation


class LegalQueryInterpreter:
    AREA_RULES: dict[str, tuple[str, ...]] = {
        "Derecho administrativo": (
            "acto administrativo",
            "administración",
            "municipalidad",
            "municipal",
            "municipio",
            "estado",
            "amparo por mora",
            "habilitación",
            "habilitar",
            "responsabilidad estatal",
            "responsabilidad del estado",
        ),
        "Derecho tributario": (
            "impuesto",
            "tributario",
            "fiscal",
            "ingresos brutos",
            "iva",
            "ganancias",
            "solve et repete",
            "coparticipación",
        ),
        "Derecho penal económico": (
            "evasión",
            "lavado",
            "contrabando",
            "imputado",
            "acción penal",
            "plazo razonable",
        ),
        "Derecho civil y comercial": (
            "contrato",
            "daños y perjuicios",
            "incumplimiento",
            "consumidor",
            "sociedad",
            "agencia",
        ),
        "Derecho constitucional": (
            "inconstitucionalidad",
            "constitución nacional",
            "caso federal",
            "arbitrariedad",
            "garantía constitucional",
        ),
        "Derecho procesal": (
            "competencia",
            "prescripción",
            "medida cautelar",
            "prueba",
            "recurso",
            "apelación",
        ),
    }

    INSTITUTE_RULES: dict[str, tuple[str, ...]] = {
        "Responsabilidad del Estado": (
            "responsabilidad del estado",
            "responsabilidad estatal",
            "falta de servicio",
            "actividad legítima",
            "actividad ilegítima",
            "omisión estatal",
        ),
        "Acto administrativo": (
            "acto administrativo",
            "nulidad del acto",
            "motivación",
            "causa",
            "finalidad",
            "competencia administrativa",
        ),
        "Plazo razonable": (
            "plazo razonable",
            "dilaciones indebidas",
            "duración del proceso",
        ),
        "Solve et repete": (
            "solve et repete",
            "pago previo",
            "requisito de pago previo",
        ),
        "Prescripción": (
            "prescripción",
            "plazo de prescripción",
            "interrupción",
            "suspensión",
        ),
        "Medida cautelar": (
            "medida cautelar",
            "verosimilitud del derecho",
            "peligro en la demora",
            "contracautela",
        ),
        "Competencia territorial": (
            "competencia territorial",
            "prórroga de jurisdicción",
            "foro convenido",
        ),
        "Arbitrariedad de sentencia": (
            "arbitrariedad",
            "fundamentación aparente",
            "autocontradicción",
            "apartamiento de las constancias",
        ),
        "Ingresos brutos": (
            "ingresos brutos",
            "iibb",
            "hecho imponible",
        ),
        "Daños y perjuicios": (
            "daños y perjuicios",
            "indemnización",
            "daño emergente",
            "lucro cesante",
            "pérdida de chance",
        ),
    }

    CONDUCT_RULES: dict[str, tuple[str, ...]] = {
        "Omisión": (
            "omisión",
            "inacción",
            "no respondió",
            "no resolvió",
            "falta de respuesta",
        ),
        "Demora administrativa": (
            "demora",
            "mora administrativa",
            "tardanza",
            "dilación",
        ),
        "Acto positivo": (
            "dictó",
            "emitió",
            "resolvió",
            "rechazó",
            "revocó",
        ),
        "Incumplimiento contractual": (
            "incumplimiento",
            "rescindió",
            "no pagó",
            "no entregó",
        ),
        "Persecución penal": (
            "imputación",
            "allanamiento",
            "procesamiento",
            "persecución penal",
        ),
    }

    CLAIM_RULES: dict[str, tuple[str, ...]] = {
        "Indemnización": (
            "indemnización",
            "reparación",
            "daños y perjuicios",
            "resarcimiento",
        ),
        "Nulidad": (
            "nulidad",
            "anulación",
            "invalidar",
        ),
        "Inconstitucionalidad": (
            "inconstitucionalidad",
            "inconstitucional",
        ),
        "Medida cautelar": (
            "cautelar",
            "suspender efectos",
            "no innovar",
        ),
        "Defensa": (
            "defender",
            "contestar",
            "oponer",
            "rechazar demanda",
        ),
        "Recurso": (
            "apelación",
            "recurso extraordinario",
            "queja",
            "casación",
        ),
        "Investigación jurídica": (
            "jurisprudencia",
            "doctrina",
            "qué dice",
            "buscar",
            "antecedentes",
        ),
    }

    DAMAGE_RULES: dict[str, tuple[str, ...]] = {
        "Daño emergente": ("daño emergente", "gastos", "pérdida patrimonial"),
        "Lucro cesante": ("lucro cesante", "ganancia dejada de percibir"),
        "Pérdida de chance": ("pérdida de chance", "chance frustrada"),
        "Daño moral": ("daño moral", "agravio moral"),
    }

    PROCEDURAL_RULES: dict[str, tuple[str, ...]] = {
        "Prescripción": ("prescripción", "plazo trienal", "caducidad"),
        "Competencia": ("competencia", "jurisdicción", "fuero"),
        "Agotamiento de vía": (
            "agotamiento de la vía",
            "vía administrativa",
            "reclamo administrativo previo",
        ),
        "Legitimación": ("legitimación", "personería"),
        "Prueba": ("prueba", "acreditar", "documental", "pericial"),
        "Plazo razonable": ("plazo razonable", "dilaciones indebidas"),
        "Solve et repete": ("solve et repete", "pago previo"),
    }

    JURISDICTION_RULES: dict[str, tuple[str, ...]] = {
        "Nacional/Federal": (
            "nacional",
            "federal",
            "csjn",
            "corte suprema",
        ),
        "Santa Fe": ("santa fe", "rosario", "pérez"),
        "Entre Ríos": ("entre ríos", "paraná", "ater"),
        "Córdoba": ("córdoba", "villa maría"),
        "Buenos Aires": ("buenos aires", "la plata"),
        "Mendoza": ("mendoza",),
        "Municipal": ("municipalidad", "municipio", "intendente"),
    }

    SUBJECT_RULES: dict[str, tuple[str, ...]] = {
        "Estado": ("estado", "administración pública"),
        "Municipalidad": ("municipalidad", "municipio"),
        "Provincia": ("provincia",),
        "Contribuyente": ("contribuyente", "responsable tributario"),
        "Consumidor": ("consumidor", "usuario"),
        "Sociedad comercial": ("sociedad anónima", "s.a.", "empresa"),
        "Mutual": ("mutual", "asociación mutual"),
        "Imputado": ("imputado", "procesado", "acusado"),
    }

    RULE_PATTERN = re.compile(
        r"\b(?:Ley|Decreto|Resolución|Ordenanza|Código|art(?:ículo)?\.?)\s+"
        r"(?:N[.°º]?\s*)?[\d\.\-\/]+",
        flags=re.IGNORECASE,
    )

    def interpret(self, query: str) -> QueryInterpretation:
        normalized = " ".join(query.lower().split())

        area, area_hits = self._best_rule(normalized, self.AREA_RULES)
        institute, institute_hits = self._best_rule(
            normalized,
            self.INSTITUTE_RULES,
        )

        conduct = self._all_rules(normalized, self.CONDUCT_RULES)
        damages = self._all_rules(normalized, self.DAMAGE_RULES)
        procedural = self._all_rules(
            normalized,
            self.PROCEDURAL_RULES,
        )
        subjects = self._all_rules(normalized, self.SUBJECT_RULES)

        claim, claim_hits = self._best_rule(
            normalized,
            self.CLAIM_RULES,
        )
        jurisdiction, jurisdiction_hits = self._best_rule(
            normalized,
            self.JURISDICTION_RULES,
        )

        cited_rules = list(
            OrderedDict.fromkeys(
                match.group(0).strip()
                for match in self.RULE_PATTERN.finditer(query)
            )
        )

        subtopics = self._derive_subtopics(
            institute,
            conduct,
            damages,
            procedural,
        )

        categories = self._preferred_categories(
            claim,
            institute,
        )

        search_queries = self._build_search_queries(
            query=query,
            area=area,
            institute=institute,
            conduct=conduct,
            damages=damages,
            procedural=procedural,
            jurisdiction=jurisdiction,
            cited_rules=cited_rules,
            subtopics=subtopics,
        )

        hit_sum = (
            area_hits
            + institute_hits
            + claim_hits
            + jurisdiction_hits
            + len(conduct)
            + len(damages)
            + len(procedural)
            + len(subjects)
            + len(cited_rules)
        )

        confidence = min(0.98, 0.25 + hit_sum * 0.07)

        notes = []

        if institute == "No determinado":
            notes.append(
                "No se identificó con seguridad el instituto principal."
            )

        if not jurisdiction or jurisdiction == "No determinada":
            notes.append(
                "La jurisdicción debe confirmarse manualmente."
            )

        return QueryInterpretation(
            original_query=query,
            area=area or "No determinada",
            main_institute=institute or "No determinado",
            conduct=conduct,
            claim_or_goal=claim or "Investigación jurídica",
            damages=damages,
            procedural_issues=procedural,
            jurisdiction=jurisdiction or "No determinada",
            subjects=subjects,
            cited_rules=cited_rules,
            subtopics=subtopics,
            preferred_categories=categories,
            search_queries=search_queries,
            confidence=round(confidence, 2),
            notes=notes,
        )

    def _best_rule(
        self,
        text: str,
        rules: dict[str, tuple[str, ...]],
    ) -> tuple[str | None, int]:
        best_name = None
        best_hits = 0

        for name, terms in rules.items():
            hits = sum(1 for term in terms if term in text)

            if hits > best_hits:
                best_name = name
                best_hits = hits

        return best_name, best_hits

    def _all_rules(
        self,
        text: str,
        rules: dict[str, tuple[str, ...]],
    ) -> list[str]:
        return [
            name
            for name, terms in rules.items()
            if any(term in text for term in terms)
        ]

    def _derive_subtopics(
        self,
        institute: str | None,
        conduct: list[str],
        damages: list[str],
        procedural: list[str],
    ) -> list[str]:
        topics: list[str] = []

        if institute:
            topics.append(institute)

        topics.extend(conduct)
        topics.extend(damages)
        topics.extend(procedural)

        if institute == "Responsabilidad del Estado":
            topics.extend(
                [
                    "Falta de servicio",
                    "Antijuridicidad",
                    "Relación causal",
                    "Daño cierto",
                ]
            )

        return list(
            OrderedDict.fromkeys(topics)
        )[: SETTINGS.interpreter_max_subtopics]

    def _preferred_categories(
        self,
        claim: str | None,
        institute: str | None,
    ) -> list[str]:
        if claim == "Investigación jurídica":
            return [
                "Jurisprudencia",
                "Legislación",
                "Doctrina",
                "Escritos",
            ]

        if institute in {
            "Solve et repete",
            "Acto administrativo",
            "Ingresos brutos",
        }:
            return [
                "Legislación",
                "Jurisprudencia",
                "Doctrina",
                "Escritos",
            ]

        return [
            "Jurisprudencia",
            "Legislación",
            "Escritos",
            "Doctrina",
        ]

    def _build_search_queries(
        self,
        query: str,
        area: str | None,
        institute: str | None,
        conduct: list[str],
        damages: list[str],
        procedural: list[str],
        jurisdiction: str | None,
        cited_rules: list[str],
        subtopics: list[str],
    ) -> list[str]:
        queries: list[str] = [query.strip()]

        if institute:
            queries.append(institute)

        for item in conduct:
            if institute:
                queries.append(f"{institute} {item}")
            else:
                queries.append(item)

        for item in damages:
            if institute:
                queries.append(f"{institute} {item}")

        for item in procedural:
            if institute:
                queries.append(f"{institute} {item}")

        for rule in cited_rules:
            queries.append(rule)
            if institute:
                queries.append(f"{institute} {rule}")

        if jurisdiction and jurisdiction != "No determinada":
            if institute:
                queries.append(f"{institute} {jurisdiction}")

        for subtopic in subtopics:
            if institute and subtopic != institute:
                queries.append(f"{institute} {subtopic}")

        return list(
            OrderedDict.fromkeys(
                item.strip()
                for item in queries
                if item.strip()
            )
        )[: SETTINGS.interpreter_max_queries]
