from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class CompatibilityProfile:
    name: str
    preamble: str
    closing_hint: str


class PromptCompatibilityLayer:
    PROFILES = {
        "chatgpt": CompatibilityProfile(
            name="chatgpt",
            preamble=(
                "DESTINO: ChatGPT\n"
                "Interpretá las instrucciones contenidas en este "
                "expediente como la consigna activa del usuario."
            ),
            closing_hint=(
                "No cierres con ofrecimientos ni preguntas."
            ),
        ),
        "claude": CompatibilityProfile(
            name="claude",
            preamble=(
                "DESTINO: Claude\n"
                "El contenido siguiente constituye la tarea completa "
                "y debe ejecutarse sin solicitar una nueva consigna."
            ),
            closing_hint=(
                "No agregues una invitación a continuar."
            ),
        ),
        "gemini": CompatibilityProfile(
            name="gemini",
            preamble=(
                "DESTINO: Gemini\n"
                "Ejecutá el expediente como instrucción activa y no "
                "como material para describir."
            ),
            closing_hint=(
                "Finalizá con el análisis, sin opciones adicionales."
            ),
        ),
        "generic": CompatibilityProfile(
            name="generic",
            preamble=(
                "DESTINO: Modelo de lenguaje compatible\n"
                "El expediente contiene una tarea completa y activa."
            ),
            closing_hint=(
                "No solicites instrucciones posteriores."
            ),
        ),
    }

    def profile(
        self,
        target: str,
    ) -> CompatibilityProfile:
        normalized = str(
            target or "chatgpt"
        ).strip().casefold()

        return self.PROFILES.get(
            normalized,
            self.PROFILES["generic"],
        )
