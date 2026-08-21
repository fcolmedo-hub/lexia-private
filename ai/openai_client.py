import json
import os
import socket
import urllib.error
import urllib.request
from dataclasses import dataclass

from config.settings import SETTINGS


class OpenAIClientError(RuntimeError):
    pass


@dataclass(slots=True)
class OpenAIStatus:
    configured: bool
    model: str
    error: str | None = None


@dataclass(slots=True)
class OpenAIAnswer:
    text: str
    input_tokens: int
    output_tokens: int
    total_tokens: int
    response_id: str


class OpenAIClient:
    def __init__(self):
        self.base_url = SETTINGS.openai_base_url.rstrip("/")
        self.model = os.getenv(
            "LEXIA_OPENAI_MODEL",
            SETTINGS.openai_model,
        )
        self.timeout = SETTINGS.openai_timeout_seconds

    @property
    def api_key(self) -> str:
        return os.getenv("OPENAI_API_KEY", "").strip()

    def status(self) -> OpenAIStatus:
        if not self.api_key:
            return OpenAIStatus(
                configured=False,
                model=self.model,
                error=(
                    "No se encontró la variable de entorno "
                    "OPENAI_API_KEY."
                ),
            )

        try:
            self._request(
                "GET",
                f"/models/{self.model}",
                timeout_seconds=20,
            )
            return OpenAIStatus(
                configured=True,
                model=self.model,
            )
        except Exception as error:
            return OpenAIStatus(
                configured=False,
                model=self.model,
                error=str(error),
            )

    def respond(
        self,
        instructions: str,
        user_input: str,
        max_output_tokens: int | None = None,
    ) -> OpenAIAnswer:
        if not self.api_key:
            raise OpenAIClientError(
                "Falta configurar OPENAI_API_KEY."
            )

        payload = {
            "model": self.model,
            "instructions": instructions,
            "input": user_input,
            "max_output_tokens": (
                max_output_tokens
                or SETTINGS.openai_max_output_tokens
            ),
            "store": SETTINGS.openai_store_responses,
        }

        if self.model.startswith(("gpt-5", "o")):
            payload["reasoning"] = {
                "effort": SETTINGS.openai_reasoning_effort
            }

        response = self._request(
            "POST",
            "/responses",
            payload,
        )

        text = self._extract_output_text(response)
        usage = response.get("usage") or {}

        return OpenAIAnswer(
            text=text,
            input_tokens=int(usage.get("input_tokens", 0) or 0),
            output_tokens=int(usage.get("output_tokens", 0) or 0),
            total_tokens=int(usage.get("total_tokens", 0) or 0),
            response_id=str(response.get("id", "")),
        )

    def _extract_output_text(self, payload: dict) -> str:
        direct = payload.get("output_text")
        if isinstance(direct, str) and direct.strip():
            return direct.strip()

        parts: list[str] = []

        for item in payload.get("output", []):
            if item.get("type") != "message":
                continue

            for content in item.get("content", []):
                if content.get("type") in {
                    "output_text",
                    "text",
                }:
                    text = content.get("text", "")
                    if isinstance(text, str) and text.strip():
                        parts.append(text.strip())

        if parts:
            return "\n\n".join(parts)

        error = payload.get("error")
        if error:
            raise OpenAIClientError(str(error))

        raise OpenAIClientError(
            "OpenAI respondió sin texto utilizable."
        )

    def _request(
        self,
        method: str,
        endpoint: str,
        payload: dict | None = None,
        timeout_seconds: int | None = None,
    ) -> dict:
        data = None
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        if payload is not None:
            data = json.dumps(
                payload,
                ensure_ascii=False,
            ).encode("utf-8")

        request = urllib.request.Request(
            self.base_url + endpoint,
            data=data,
            headers=headers,
            method=method,
        )

        try:
            with urllib.request.urlopen(
                request,
                timeout=timeout_seconds or self.timeout,
            ) as response:
                return json.loads(
                    response.read().decode("utf-8")
                )

        except urllib.error.HTTPError as error:
            detail = error.read().decode(
                "utf-8",
                errors="replace",
            )
            raise OpenAIClientError(
                f"OpenAI devolvió HTTP {error.code}: {detail}"
            ) from error

        except (TimeoutError, socket.timeout) as error:
            raise OpenAIClientError(
                "OpenAI superó el tiempo máximo de espera."
            ) from error

        except urllib.error.URLError as error:
            raise OpenAIClientError(
                "No se pudo conectar con OpenAI. "
                "Verificá Internet y la clave de API."
            ) from error
