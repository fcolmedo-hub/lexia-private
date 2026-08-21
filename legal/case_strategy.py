from dataclasses import dataclass, field


@dataclass(slots=True)
class StrategyReport:
    thesis: str
    favorable_points: list[str] = field(default_factory=list)
    adverse_points: list[str] = field(default_factory=list)
    missing_evidence: list[str] = field(default_factory=list)
    procedural_risks: list[str] = field(default_factory=list)
    next_actions: list[str] = field(default_factory=list)

    def to_markdown(self) -> str:
        def block(title: str, values: list[str]) -> str:
            body = "\n".join(f"- {value}" for value in values) or "- Sin elementos."
            return f"## {title}\n\n{body}"

        return "\n\n".join(
            [
                f"# Estrategia del caso\n\n**Tesis:** {self.thesis}",
                block("Puntos favorables", self.favorable_points),
                block("Puntos adversos", self.adverse_points),
                block("Prueba faltante", self.missing_evidence),
                block("Riesgos procesales", self.procedural_risks),
                block("Próximas acciones", self.next_actions),
            ]
        )


class CaseStrategyEngine:
    def build(
        self,
        thesis: str,
        facts: str,
        evidence: str,
        adverse_position: str,
        sources_count: int,
    ) -> StrategyReport:
        favorable = []
        adverse = []
        missing = []
        risks = []

        if thesis.strip():
            favorable.append("La tesis principal fue definida expresamente.")
        else:
            adverse.append("No existe una tesis principal claramente formulada.")

        if facts.strip():
            favorable.append("Se incorporó una base fáctica para la estrategia.")
        else:
            missing.append("Falta una relación ordenada de los hechos relevantes.")

        if evidence.strip():
            favorable.append("Se identificó prueba disponible.")
        else:
            missing.append("No se detalló la prueba que respalda los hechos.")

        if sources_count:
            favorable.append(
                f"Se seleccionaron {sources_count} fuentes jurídicas."
            )
        else:
            adverse.append("No se seleccionaron fuentes jurídicas verificables.")

        if adverse_position.strip():
            favorable.append("La posición contraria fue identificada.")
        else:
            adverse.append(
                "No se explicitó el principal contraargumento de la contraparte."
            )

        risks.extend(
            [
                "Controlar competencia, legitimación y prescripción.",
                "Verificar la correspondencia entre cada hecho y su prueba.",
                "Revisar jurisprudencia adversa de mayor autoridad.",
                "Alinear fundamentos, estrategia y petitorio.",
            ]
        )

        actions = [
            "Completar la matriz hecho–prueba–derecho.",
            "Seleccionar precedentes favorables y adversos.",
            "Definir la pretensión concreta y subsidiaria.",
            "Preparar un borrador por capítulos.",
        ]

        return StrategyReport(
            thesis=thesis.strip() or "[Tesis pendiente]",
            favorable_points=favorable,
            adverse_points=adverse,
            missing_evidence=missing,
            procedural_risks=risks,
            next_actions=actions,
        )
