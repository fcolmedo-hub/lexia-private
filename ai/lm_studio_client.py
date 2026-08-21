import json
import urllib.error
import urllib.request
from dataclasses import dataclass

from config.settings import SETTINGS


class LMStudioError(RuntimeError):
    pass


@dataclass(slots=True)
class LMStudioStatus:
    connected: bool
    models: list[str]
    active_model: str
    error: str | None = None


class LMStudioClient:
    def __init__(self):
        self.base_url = SETTINGS.lm_studio_base_url.rstrip("/")
        self.model = SETTINGS.lm_studio_model
        self.timeout = SETTINGS.lm_studio_timeout_seconds

    def status(self) -> LMStudioStatus:
        try:
            payload = self._request("GET", "/models")
            models = [
                str(item.get("id", ""))
                for item in payload.get("data", [])
            ]
            return LMStudioStatus(
                connected=True,
                models=[item for item in models if item],
                active_model=self.model,
            )
        except Exception as error:
            return LMStudioStatus(
                False,
                [],
                self.model,
                str(error),
            )

    def chat(
        self,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int | None = None,
        temperature: float | None = None,
    ) -> str:
        # Primer intento con el contexto calculado por LexIA.
        attempts = (
            user_prompt,
            self._shrink(user_prompt, 0.78),
            self._shrink(user_prompt, 0.58),
        )

        last_error: Exception | None = None

        for prompt in attempts:
            payload = {
                "model": self.model,
                "messages": [
                    {
                        "role": "system",
                        "content": system_prompt,
                    },
                    {
                        "role": "user",
                        "content": prompt,
                    },
                ],
                "temperature": (
                    SETTINGS.ai_temperature
                    if temperature is None
                    else temperature
                ),
                "max_tokens": (
                    SETTINGS.ai_max_tokens
                    if max_tokens is None
                    else max_tokens
                ),
                "stream": False,
            }

            try:
                response = self._request(
                    "POST",
                    "/chat/completions",
                    payload,
                )
                return str(
                    response["choices"][0]["message"]["content"]
                ).strip()

            except LMStudioError as error:
                last_error = error
                message = str(error).lower()

                if (
                    "context length" not in message
                    and "n_keep" not in message
                    and "n_ctx" not in message
                ):
                    raise

        raise LMStudioError(
            "El contexto sigue siendo demasiado largo para el modelo "
            "cargado con 4096 tokens. Reducí la cantidad de fuentes o "
            "cargá Mistral con una ventana de contexto mayor."
        ) from last_error

    def _shrink(
        self,
        text: str,
        ratio: float,
    ) -> str:
        target = max(1800, int(len(text) * ratio))

        if len(text) <= target:
            return text

        # Conserva el problema jurídico del inicio y la instrucción final.
        head_size = int(target * 0.82)
        tail_size = target - head_size

        return (
            text[:head_size].rstrip()
            + "\n\n[CONTEXTO REDUCIDO AUTOMÁTICAMENTE]\n\n"
            + text[-tail_size:].lstrip()
        )

    def _request(
        self,
        method: str,
        endpoint: str,
        payload: dict | None = None,
    ) -> dict:
        data = None
        headers = {"Content-Type": "application/json"}

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
                timeout=self.timeout,
            ) as response:
                return json.loads(
                    response.read().decode("utf-8")
                )

        except urllib.error.HTTPError as error:
            detail = error.read().decode(
                "utf-8",
                errors="replace",
            )
            raise LMStudioError(
                f"LM Studio devolvió HTTP {error.code}: {detail}"
            ) from error

        except urllib.error.URLError as error:
            raise LMStudioError(
                "No se pudo conectar con LM Studio. Verificá que "
                "el servidor esté Running en "
                "http://127.0.0.1:1234."
            ) from error
