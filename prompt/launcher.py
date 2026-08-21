from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class LaunchInstruction:
    target: str
    title: str
    prompt: str
    filename: str

    def as_text(self) -> str:
        return self.prompt.strip() + "\n"


class PromptLauncher:
    """
    Genera la consigna visible que el usuario debe enviar junto con el
    expediente .lexia. No modifica el expediente ni consulta servicios
    externos.
    """

    TEMPLATES = {
        "chatgpt": (
            "Ejecutá inmediatamente el expediente .lexia adjunto "
            "conforme a su protocolo interno y a la tarea específica "
            "que contiene. No solicites aclaraciones, no describas el "
            "archivo y no ofrezcas opciones. Elaborá directamente el "
            "análisis jurídico, exclusivamente sobre las fuentes "
            "[FUENTE N] incorporadas, sin Internet ni conocimiento "
            "externo."
        ),
        "claude": (
            "Tratà el expediente .lexia adjunto como la consigna activa "
            "y completa de esta conversación. Ejecutá inmediatamente la "
            "tarea jurídica contenida en él. No resumas el archivo, no "
            "pidas una nueva instrucción y no uses información externa "
            "a las fuentes [FUENTE N]."
        ),
        "gemini": (
            "Usá el expediente .lexia adjunto como contexto cerrado y "
            "ejecutá de inmediato la tarea jurídica definida dentro del "
            "archivo. No pidas confirmación, no describas el adjunto y "
            "no agregues información ajena a las fuentes [FUENTE N]."
        ),
        "generic": (
            "Ejecutá inmediatamente la tarea contenida en el expediente "
            ".lexia adjunto. Considerá el archivo como contexto jurídico "
            "cerrado. No solicites una nueva consigna, no lo resumas y no "
            "uses fuentes externas."
        ),
    }

    TITLES = {
        "chatgpt": "Consigna para ChatGPT",
        "claude": "Consigna para Claude",
        "gemini": "Consigna para Gemini",
        "generic": "Consigna genérica",
    }

    def generate(
        self,
        target: str = "chatgpt",
        *,
        objective: str = "",
        query: str = "",
        file_name: str = "",
    ) -> LaunchInstruction:
        normalized = str(target or "chatgpt").strip().casefold()

        if normalized not in self.TEMPLATES:
            normalized = "generic"

        prompt = self.TEMPLATES[normalized]

        context_lines = []

        if objective.strip():
            context_lines.append(
                f"Objetivo declarado por LexIA: {objective.strip()}."
            )

        if query.strip():
            context_lines.append(
                f"Consulta incorporada: {query.strip()}"
            )

        if file_name.strip():
            context_lines.append(
                f"Archivo: {Path(file_name).name}"
            )

        if context_lines:
            prompt = (
                prompt
                + "\n\n"
                + "\n".join(context_lines)
            )

        return LaunchInstruction(
            target=normalized,
            title=self.TITLES[normalized],
            prompt=prompt,
            filename=(
                f"consigna_{normalized}.txt"
            ),
        )
