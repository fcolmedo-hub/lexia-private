import re

from prompt.compatibility import (
    PromptCompatibilityLayer,
)
from prompt.models import (
    PromptCompilationResult,
)
from prompt.optimizer import PromptOptimizer
from prompt.protocol import LexIAPromptProtocol
from prompt.renderer import PromptRenderer
from prompt.validator import PromptValidator


class PromptCompilationError(RuntimeError):
    pass


class PromptCompiler:
    def __init__(self):
        self.protocol = LexIAPromptProtocol()
        self.compatibility = (
            PromptCompatibilityLayer()
        )
        self.optimizer = PromptOptimizer()
        self.renderer = PromptRenderer()
        self.validator = PromptValidator()

    def compile(
        self,
        body: str,
        *,
        target: str = "chatgpt",
        expected_source_count: int | None = None,
    ) -> PromptCompilationResult:
        if not str(body).strip():
            raise PromptCompilationError(
                "El cuerpo del expediente está vacío."
            )

        original = str(body)
        cleaned = self._remove_legacy_bootstrap(
            original
        )
        optimized_body = self.optimizer.optimize(
            cleaned
        )
        profile = self.compatibility.profile(
            target
        )
        rendered = self.renderer.render(
            optimized_body,
            profile,
            self.protocol,
        )
        compiled = self.optimizer.optimize(
            rendered
        )
        validation = self.validator.validate(
            compiled,
            expected_source_count=(
                expected_source_count
            ),
        )

        if not validation.valid:
            detail = "; ".join(
                issue.message
                for issue in validation.errors
            )
            raise PromptCompilationError(
                "El expediente .lexia no superó la "
                f"validación: {detail}"
            )

        source_count = len(
            set(
                re.findall(
                    r"(?m)^\[FUENTE (\d+)\]\s*$",
                    compiled,
                )
            )
        )

        return PromptCompilationResult(
            content=compiled,
            target=profile.name,
            protocol_version=(
                self.protocol.VERSION
            ),
            validation=validation,
            original_character_count=len(
                original
            ),
            compiled_character_count=len(
                compiled
            ),
            source_count=source_count,
        )

    def _remove_legacy_bootstrap(
        self,
        body: str,
    ) -> str:
        # Mantiene el contenido jurídico, pero evita tener dos protocolos
        # de arranque contradictorios dentro del mismo expediente.
        patterns = (
            (
                r"(?s)## INSTRUCCIÓN PRINCIPAL PARA CHATGPT\s+"
                r".*?(?=\n## TAREA ESPECÍFICA)",
                (
                    "## INSTRUCCIONES JURÍDICAS DE LA TAREA\n\n"
                    "Aplicá el protocolo general de ejecución y "
                    "evidencia establecido al comienzo."
                ),
            ),
            (
                r"(?s)## ORDEN FINAL\s+.*$",
                "",
            ),
        )

        output = body

        for pattern, replacement in patterns:
            output = re.sub(
                pattern,
                replacement,
                output,
                count=1,
            )

        return output.strip()
