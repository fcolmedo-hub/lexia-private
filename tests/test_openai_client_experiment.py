import json

from ai.openai_client import OpenAIClient


class RecordingOpenAIClient(OpenAIClient):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.request_payload = None

    @property
    def api_key(self) -> str:
        return "test-key"

    def _request(
        self,
        method,
        endpoint,
        payload=None,
        timeout_seconds=None,
    ):
        self.request_payload = json.loads(json.dumps(payload))
        return {
            "id": "resp_experiment",
            "output_text": "Respuesta jurídica",
            "usage": {
                "input_tokens": 10,
                "output_tokens": 20,
                "total_tokens": 30,
            },
        }


def test_sol_high_direct_request_omits_instructions_and_structured_output():
    client = RecordingOpenAIClient(
        model="gpt-5.6-sol",
        reasoning_effort="high",
    )
    exported_context = "# PAQUETE DE INVESTIGACIÓN JURÍDICA — LEXIA"

    client.respond(
        instructions=None,
        user_input=exported_context,
    )

    payload = client.request_payload
    assert payload["model"] == "gpt-5.6-sol"
    assert payload["reasoning"] == {"effort": "high"}
    assert payload["input"] == exported_context
    assert "instructions" not in payload
    assert "text" not in payload
