from dataclasses import dataclass

from models.search_result import SearchResult


@dataclass(slots=True)
class ArgumentDraft:
    title: str
    content: str


class ArgumentBuilder:
    def build(
        self,
        thesis: str,
        facts: str,
        sources: list[SearchResult],
        opposing_point: str = "",
        requested_relief: str = "",
    ) -> ArgumentDraft:
        source_lines = []

        for number, source in enumerate(sources, start=1):
            metadata = source.metadata or {}
            source_lines.append(
                f"{number}. {source.citation_label()}\n"
                f"   Tribunal: {metadata.get('court', 'No detectado')}\n"
                f"   Fecha: {metadata.get('date', 'No detectada')}\n"
                f"   Normas: {metadata.get('laws', 'No detectadas')}\n"
                f"   Ruta: {source.document_path}\n"
                f"   Extracto: {source.text[:700].strip()}"
            )

        source_block = (
            "\n\n".join(source_lines)
            if source_lines
            else "No se seleccionaron fuentes."
        )

        content = (
            f"# {thesis.strip() or 'Argumento jurídico'}\n\n"
            "## 1. Tesis\n\n"
            f"{thesis.strip() or '[Completar tesis]'}\n\n"
            "## 2. Hechos relevantes\n\n"
            f"{facts.strip() or '[Completar hechos]'}\n\n"
            "## 3. Regla jurídica propuesta\n\n"
            "Identificar la norma, principio o doctrina aplicable y "
            "formularla de manera precisa, evitando generalizaciones "
            "que no estén respaldadas por las fuentes.\n\n"
            "## 4. Subsunción\n\n"
            "Explicar, hecho por hecho, por qué la situación concreta "
            "queda comprendida en la regla jurídica invocada. Cada "
            "afirmación fáctica relevante debe vincularse con prueba.\n\n"
            "## 5. Jurisprudencia, doctrina y normativa\n\n"
            f"{source_block}\n\n"
            "## 6. Posición contraria\n\n"
            f"{opposing_point.strip() or '[No indicada]'}\n\n"
            "## 7. Respuesta al contraargumento\n\n"
            "Distinguir los precedentes adversos, cuestionar sus "
            "premisas cuando corresponda y demostrar por qué los hechos "
            "del caso conducen a una solución diferente.\n\n"
            "## 8. Riesgos y prueba faltante\n\n"
            "- Verificar que cada hecho central tenga respaldo documental.\n"
            "- Controlar vigencia, jurisdicción y autoridad de cada fuente.\n"
            "- Identificar la mejor objeción procesal de la contraparte.\n"
            "- Revisar coherencia entre fundamentos y petición.\n\n"
            "## 9. Petición o consecuencia jurídica\n\n"
            f"{requested_relief.strip() or '[Completar petición concreta]'}\n\n"
            "## 10. Control de trazabilidad\n\n"
            "- No incorporar hechos no suministrados.\n"
            "- Verificar todas las citas en el documento original.\n"
            "- Separar texto de fuente, inferencia y recomendación.\n"
        )

        return ArgumentDraft(
            title=thesis.strip() or "Argumento jurídico",
            content=content,
        )
