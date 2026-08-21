from __future__ import annotations


class LegalQueryExpander:
    """
    Expansor jurídico determinista para consultas breves.

    No reemplaza al Query Interpreter existente:
    agrega variantes controladas a interpretation.search_queries.
    """

    RULES = (
        (
            ("plazo razonable", "duración razonable"),
            (
                "plazo razonable proceso",
                "duración razonable del proceso",
                "demora judicial indebida",
                "artículo 8 Convención Americana plazo razonable",
                "garantía de ser juzgado en plazo razonable",
            ),
        ),
        (
            ("prescripción", "prescripcion"),
            (
                "prescripción de la acción",
                "interrupción de la prescripción",
                "suspensión de la prescripción",
            ),
        ),
        (
            ("recurso extraordinario",),
            (
                "recurso extraordinario federal",
                "arbitrariedad de sentencia",
                "cuestión federal",
                "sentencia definitiva",
            ),
        ),
        (
            ("solve et repete", "pago previo"),
            (
                "solve et repete",
                "requisito de pago previo",
                "acceso a la justicia pago previo",
                "tutela judicial efectiva solve et repete",
            ),
        ),
        (
            ("agotamiento de marca", "agotamiento marcario"),
            (
                "agotamiento del derecho de marca",
                "agotamiento internacional de marca",
                "importaciones paralelas marca",
            ),
        ),
        (
            ("importación paralela", "importacion paralela"),
            (
                "importaciones paralelas",
                "agotamiento internacional de marca",
                "distribuidor oficial marca",
            ),
        ),
        (
            ("responsabilidad del estado",),
            (
                "responsabilidad estatal",
                "actividad legítima del Estado",
                "actividad ilegítima del Estado",
                "daño cierto responsabilidad estatal",
            ),
        ),
        (
            ("medida cautelar", "cautelar"),
            (
                "verosimilitud del derecho",
                "peligro en la demora",
                "tutela cautelar",
            ),
        ),
        (
            ("debido proceso",),
            (
                "debido proceso legal",
                "defensa en juicio",
                "tutela judicial efectiva",
            ),
        ),
        (
            ("non bis in idem", "ne bis in idem"),
            (
                "non bis in idem",
                "ne bis in idem",
                "doble persecución penal",
            ),
        ),
        (
            ("principio de legalidad tributaria", "legalidad tributaria"),
            (
                "principio de reserva de ley tributaria",
                "legalidad tributaria",
                "reserva de ley en materia tributaria",
            ),
        ),
        (
            ("confiscatoriedad",),
            (
                "tributo confiscatorio",
                "confiscatoriedad tributaria",
                "afectación sustancial del patrimonio",
            ),
        ),
    )

    def expand(
        self,
        query: str,
        existing_queries=None,
        max_queries: int = 10,
    ) -> list[str]:
        max_queries = max(1, int(max_queries))
        output = []
        seen = set()

        def add(value):
            clean = " ".join(str(value or "").split()).strip()
            key = clean.casefold()
            if clean and key not in seen and len(output) < max_queries:
                output.append(clean)
                seen.add(key)

        add(query)

        for value in list(existing_queries or []):
            add(value)

        normalized = str(query or "").casefold()

        for triggers, expansions in self.RULES:
            if not any(trigger in normalized for trigger in triggers):
                continue

            for expansion in expansions:
                add(expansion)

            if len(output) >= max_queries:
                break

        return output
