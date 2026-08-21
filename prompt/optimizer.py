import re


class PromptOptimizer:
    """
    Optimizador conservador.

    Solo normaliza espacios, repeticiones exactas contiguas y saltos de
    línea. Nunca resume fuentes ni altera contenido jurídico.
    """

    def optimize(
        self,
        content: str,
    ) -> str:
        normalized = content.replace(
            "\r\n",
            "\n",
        ).replace(
            "\r",
            "\n",
        )
        normalized = re.sub(
            r"[ \t]+\n",
            "\n",
            normalized,
        )
        normalized = re.sub(
            r"\n{4,}",
            "\n\n\n",
            normalized,
        )

        lines = normalized.splitlines()
        output: list[str] = []
        previous = None

        for line in lines:
            stripped = line.strip()

            if (
                stripped
                and previous == stripped
                and not stripped.startswith(
                    "[FUENTE "
                )
            ):
                continue

            output.append(line)
            previous = (
                stripped
                if stripped
                else None
            )

        return "\n".join(output).strip() + "\n"
