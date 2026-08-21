from prompt.compatibility import (
    CompatibilityProfile,
)
from prompt.protocol import LexIAPromptProtocol


class PromptRenderer:
    def render(
        self,
        body: str,
        profile: CompatibilityProfile,
        protocol: LexIAPromptProtocol,
    ) -> str:
        return "\n\n".join(
            [
                protocol.BOOTSTRAP,
                profile.preamble,
                protocol.RUNTIME,
                protocol.EVIDENCE,
                body.strip(),
                protocol.SELF_CHECK,
                profile.closing_hint,
                protocol.CLOSING,
                (
                    "######################################################################\n"
                    "# FIN DEL EXPEDIENTE — EJECUTAR AHORA\n"
                    "######################################################################"
                ),
            ]
        ).strip() + "\n"
