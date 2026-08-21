from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ProviderInfo:
    name: str
    mode: str
    available: bool
    description: str


class ProviderRegistry:
    def list(self):
        return [
            ProviderInfo(
                "LexIA Local",
                "local",
                True,
                "Interpretación y síntesis local sin APIs externas.",
            ),
            ProviderInfo(
                "OpenAI",
                "openai",
                False,
                "Adaptador reservado; requiere configuración explícita.",
            ),
            ProviderInfo(
                "Claude",
                "claude",
                False,
                "Adaptador reservado; requiere configuración explícita.",
            ),
        ]
