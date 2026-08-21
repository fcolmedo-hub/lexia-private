from collections import OrderedDict

LEGAL_THESAURUS: dict[str, tuple[str, ...]] = {
    "responsabilidad del estado": (
        "responsabilidad estatal", "falta de servicio",
        "actividad estatal ilegítima", "omisión estatal",
        "responsabilidad extracontractual del estado",
    ),
    "actividad legítima": (
        "actividad lícita del estado", "sacrificio especial",
        "daño especial", "responsabilidad por acto lícito",
    ),
    "plazo razonable": (
        "duración razonable del proceso", "dilaciones indebidas",
        "exceso temporal del proceso", "ser juzgado sin dilaciones",
    ),
    "solve et repete": (
        "pago previo", "requisito de pago previo",
        "tutela judicial efectiva", "artículo 101 código fiscal",
        "ley convenio", "alberdi", "aca salud",
    ),
    "acto administrativo": (
        "elementos esenciales del acto administrativo", "competencia",
        "causa", "objeto", "procedimiento", "motivación",
        "finalidad", "ley 19.549", "artículo 7",
    ),
    "ley convenio": (
        "ley 23.548", "coparticipación federal",
        "obligaciones provinciales", "prohibiciones tributarias",
    ),
    "medida cautelar": (
        "tutela cautelar", "verosimilitud del derecho",
        "peligro en la demora", "contracautela", "no innovar",
    ),
    "arbitrariedad": (
        "sentencia arbitraria", "fundamentación aparente",
        "autocontradicción", "apartamiento de las constancias",
    ),
    "prescripción": (
        "extinción de la acción", "plazo de prescripción",
        "interrupción de la prescripción", "suspensión de la prescripción",
    ),
}

class LegalQueryExpander:
    def expand(self, query: str, max_expansions: int = 10) -> list[str]:
        normalized = " ".join(query.lower().split())
        variants: list[str] = [query.strip()]
        for key, synonyms in LEGAL_THESAURUS.items():
            if key in normalized or any(s in normalized for s in synonyms):
                variants.extend(synonyms)
        tokens = set(normalized.split())
        if {"estado", "demora"} <= tokens:
            variants.extend([
                "omisión administrativa", "mora administrativa",
                "inactividad de la administración",
                "falta de servicio por demora",
            ])
        return list(OrderedDict.fromkeys(v.strip() for v in variants if v.strip()))[:max_expansions + 1]
