from dataclasses import dataclass, field


@dataclass(slots=True)
class CopilotResponse:
    summary: str
    issues: list[str] = field(default_factory=list)
    sources: list[str] = field(default_factory=list)
    risks: list[str] = field(default_factory=list)
    actions: list[str] = field(default_factory=list)

    def to_markdown(self):
        def block(title, items):
            body = "\n".join(f"- {item}" for item in items) or "- Sin elementos."
            return f"## {title}\n\n{body}"
        return "\n\n".join([
            f"# Informe jurídico preliminar\n\n{self.summary}",
            block("Cuestiones jurídicas", self.issues),
            block("Fuentes recuperadas", self.sources),
            block("Riesgos", self.risks),
            block("Acciones sugeridas", self.actions),
        ])


class LocalLegalCopilot:
    def build(self, interpretation, sources):
        issues = list(dict.fromkeys([
            interpretation.main_institute,
            *interpretation.subtopics,
            *interpretation.procedural_issues,
        ]))
        source_lines = [
            f"{source.document_name} — {source.page_label}: "
            f"{source.text[:280].strip()}"
            for source in sources[:10]
        ]
        return CopilotResponse(
            summary=(
                f"LexIA interpretó la consulta dentro de "
                f"{interpretation.area}, con eje en "
                f"{interpretation.main_institute}. "
                f"Se recuperaron {len(sources)} fuentes."
            ),
            issues=[i for i in issues if i and not i.startswith("No ")],
            sources=source_lines,
            risks=[
                "Verificar cada cita en el documento original.",
                "Buscar y distinguir jurisprudencia adversa.",
                "Controlar competencia, prescripción, legitimación y prueba.",
            ],
            actions=[
                "Seleccionar las mejores fuentes.",
                "Completar la matriz hecho–prueba–derecho.",
                "Construir el argumento solo con hechos confirmados.",
            ],
        )
