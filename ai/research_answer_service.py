from __future__ import annotations

import os
from dataclasses import dataclass

from ai.openai_client import OpenAIClient, OpenAIClientError


class ResearchAnswerServiceError(RuntimeError):
    pass


@dataclass(slots=True)
class ResearchAnswer:
    text: str
    model: str
    reasoning_effort: str
    prompt_mode: str
    response_id: str
    input_tokens: int
    output_tokens: int
    total_tokens: int


class ResearchAnswerService:
    """Convierte un paquete interno de LexIA en una respuesta jurídica final."""

    DIRECT_PACKAGE_MODEL = "gpt-5.6-sol"
    DIRECT_PACKAGE_REASONING_EFFORT = "high"

    INSTRUCTIONS = """
Sos el motor de análisis jurídico de LexIA.
Seguí estrictamente las reglas, la tarea y las fuentes incluidas en el paquete.
Respondé en español, en formato Markdown claro y profesional.
No describas el paquete ni reproduzcas sus instrucciones: entregá directamente el análisis.
No uses fuentes externas ni inventes citas, normas, hechos o precedentes.
""".strip()

    def __init__(self, client=None, *, direct_package_experiment: bool = False):
        self.direct_package_experiment = bool(direct_package_experiment)
        if client is not None:
            self.client = client
        elif self.direct_package_experiment:
            self.client = OpenAIClient(
                model=os.getenv(
                    "LEXIA_RESEARCH_EXPERIMENT_MODEL",
                    self.DIRECT_PACKAGE_MODEL,
                ),
                reasoning_effort=os.getenv(
                    "LEXIA_RESEARCH_EXPERIMENT_REASONING_EFFORT",
                    self.DIRECT_PACKAGE_REASONING_EFFORT,
                ),
            )
        else:
            self.client = OpenAIClient()

    def answer(self, package_content: str) -> ResearchAnswer:
        content = str(package_content or "")
        if not content.strip():
            raise ResearchAnswerServiceError(
                "El paquete de investigación está vacío."
            )
        try:
            answer = self.client.respond(
                instructions=(
                    None
                    if self.direct_package_experiment
                    else self.INSTRUCTIONS
                ),
                user_input=content,
            )
        except OpenAIClientError as error:
            raise ResearchAnswerServiceError(str(error)) from error

        text = str(getattr(answer, "text", "") or "").strip()
        if not text:
            raise ResearchAnswerServiceError(
                "ChatGPT no devolvió un resultado utilizable."
            )
        return ResearchAnswer(
            text=text,
            model=str(getattr(self.client, "model", "") or ""),
            reasoning_effort=str(
                getattr(self.client, "reasoning_effort", "") or ""
            ),
            prompt_mode=(
                "direct_context_package"
                if self.direct_package_experiment
                else "lexia_instructions_plus_context_package"
            ),
            response_id=str(getattr(answer, "response_id", "") or ""),
            input_tokens=int(getattr(answer, "input_tokens", 0) or 0),
            output_tokens=int(getattr(answer, "output_tokens", 0) or 0),
            total_tokens=int(getattr(answer, "total_tokens", 0) or 0),
        )
