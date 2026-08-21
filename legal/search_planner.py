from dataclasses import dataclass, field

from models.query_interpretation import QueryInterpretation


@dataclass(slots=True)
class SearchPlan:
    main_query: str
    queries: list[str] = field(default_factory=list)
    category_order: list[str] = field(default_factory=list)
    strategy_notes: list[str] = field(default_factory=list)


class LegalSearchPlanner:
    def build(
        self,
        interpretation: QueryInterpretation,
    ) -> SearchPlan:
        notes = [
            "Ejecutar primero la consulta original.",
            "Ejecutar luego consultas especializadas por instituto y subtema.",
            "Combinar resultados y eliminar duplicados por documento.",
            "Priorizar las categorías indicadas por la interpretación.",
        ]

        if interpretation.cited_rules:
            notes.append(
                "Reservar una búsqueda específica para cada norma citada."
            )

        if interpretation.jurisdiction != "No determinada":
            notes.append(
                "Aplicar la jurisdicción como criterio de reordenamiento."
            )

        return SearchPlan(
            main_query=interpretation.original_query,
            queries=interpretation.search_queries,
            category_order=interpretation.preferred_categories,
            strategy_notes=notes,
        )
