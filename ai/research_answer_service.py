from __future__ import annotations

from dataclasses import dataclass

from ai.openai_client import OpenAIClient, OpenAIClientError


class ResearchAnswerServiceError(RuntimeError):
    pass


@dataclass(slots=True)
class ResearchAnswer:
    text: str
    model: str
    response_id: str
    input_tokens: int
    output_tokens: int
    total_tokens: int


class ResearchAnswerService:
    """Convierte un paquete interno de LexIA en una respuesta jurídica final."""

    INSTRUCTIONS = """
Sos el motor de análisis jurídico de LexIA.
Seguí estrictamente las reglas, la tarea y las fuentes incluidas en el paquete.
Respondé en español, en formato Markdown claro y profesional.
No describas el paquete ni reproduzcas sus instrucciones: entregá directamente el análisis.
No uses fuentes externas ni inventes citas, normas, hechos o precedentes.
""".strip()

    def __init__(self, client=None):
        self.client = client or OpenAIClient()

    def answer(self, package_content: str) -> ResearchAnswer:
        content = str(package_content or "").strip()
        if not content:
            raise ResearchAnswerServiceError(
                "El paquete de investigación está vacío."
            )
        try:
            answer = self.client.respond(
                instructions=self.INSTRUCTIONS,
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
            response_id=str(getattr(answer, "response_id", "") or ""),
            input_tokens=int(getattr(answer, "input_tokens", 0) or 0),
            output_tokens=int(getattr(answer, "output_tokens", 0) or 0),
            total_tokens=int(getattr(answer, "total_tokens", 0) or 0),
        )
