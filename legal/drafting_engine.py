class DraftingEngine:
    TEMPLATES = {
        "Demanda": [
            "Objeto",
            "Hechos",
            "Responsabilidad",
            "Daños",
            "Prueba",
            "Derecho",
            "Petitorio",
        ],
        "Contestación de demanda": [
            "Objeto",
            "Negativas",
            "Versión de los hechos",
            "Defensas",
            "Prueba",
            "Derecho",
            "Petitorio",
        ],
        "Recurso": [
            "Objeto",
            "Admisibilidad",
            "Agravios",
            "Arbitrariedad",
            "Caso federal",
            "Petitorio",
        ],
        "Medida cautelar": [
            "Objeto",
            "Verosimilitud del derecho",
            "Peligro en la demora",
            "Contracautela",
            "Petitorio",
        ],
    }

    def build_outline(
        self,
        document_type: str,
        thesis: str,
        facts: str,
        sources: list,
    ) -> str:
        sections = self.TEMPLATES.get(
            document_type,
            ["Objeto", "Hechos", "Derecho", "Prueba", "Petitorio"],
        )

        source_lines = [
            f"- {source.citation_label()}"
            for source in sources[:15]
        ]

        parts = [
            f"# {document_type}",
            "",
            f"**Tesis central:** {thesis.strip() or '[Completar]'}",
            "",
            "## Hechos suministrados",
            "",
            facts.strip() or "[Completar hechos]",
            "",
            "## Fuentes seleccionadas",
            "",
            "\n".join(source_lines) or "- Sin fuentes seleccionadas",
            "",
        ]

        for section in sections:
            parts.extend(
                [
                    f"## {section}",
                    "",
                    f"[Desarrollar {section.lower()} con base en hechos y fuentes verificadas.]",
                    "",
                ]
            )

        parts.extend(
            [
                "## Control final",
                "",
                "- Verificar cada cita.",
                "- Vincular hechos con prueba.",
                "- Revisar coherencia con el petitorio.",
                "- Distinguir jurisprudencia adversa.",
            ]
        )

        return "\n".join(parts)
