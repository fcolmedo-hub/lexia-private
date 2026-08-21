import re

from prompt.models import (
    PromptValidationIssue,
    PromptValidationResult,
)
from prompt.protocol import LexIAPromptProtocol


class PromptValidator:
    REQUIRED_SECTIONS = (
        "LEXIA PROMPT PROTOCOL 2.0",
        "ESTADO DE EJECUCIÓN: RUNNING",
        "## CONSULTA JURÍDICA",
        "## TAREA ESPECÍFICA",
        "## ÍNDICE DE FUENTES",
        "## FUENTES",
        "## PROTOCOLO DE EVIDENCIA",
        "## CONTROL PREVIO SILENCIOSO",
    )

    FORBIDDEN_ACTIVE_PATTERNS = (
        (
            "internet_required",
            re.compile(
                r"(?i)\b(?:buscá|consulta|consultá|navegá)"
                r".{0,30}\binternet\b"
            ),
        ),
        (
            "english_required",
            re.compile(
                r"(?i)\brespond(?:é|e|er)\s+en\s+ingl[eé]s\b"
            ),
        ),
    )

    def validate(
        self,
        content: str,
        expected_source_count: int | None = None,
    ) -> PromptValidationResult:
        issues: list[PromptValidationIssue] = []

        for section in self.REQUIRED_SECTIONS:
            if section not in content:
                issues.append(
                    PromptValidationIssue(
                        code="missing_section",
                        severity="error",
                        message=(
                            "Falta una sección obligatoria: "
                            f"{section}"
                        ),
                        location=section,
                    )
                )

        indexed = {
            int(value)
            for value in re.findall(
                r"(?m)^- \[FUENTE (\d+)\]",
                content,
            )
        }
        blocks = {
            int(value)
            for value in re.findall(
                r"(?m)^\[FUENTE (\d+)\]\s*$",
                content,
            )
        }

        if indexed != blocks:
            issues.append(
                PromptValidationIssue(
                    code="source_index_mismatch",
                    severity="error",
                    message=(
                        "El índice de fuentes y los bloques "
                        "de contenido no coinciden."
                    ),
                    location="ÍNDICE DE FUENTES / FUENTES",
                )
            )

        source_count = len(blocks)

        if (
            expected_source_count is not None
            and source_count != expected_source_count
        ):
            issues.append(
                PromptValidationIssue(
                    code="source_count_mismatch",
                    severity="error",
                    message=(
                        "La cantidad compilada de fuentes "
                        f"({source_count}) no coincide con la "
                        f"esperada ({expected_source_count})."
                    ),
                    location="FUENTES",
                )
            )

        if blocks:
            expected = set(
                range(
                    1,
                    max(blocks) + 1,
                )
            )
            if blocks != expected:
                issues.append(
                    PromptValidationIssue(
                        code="non_contiguous_sources",
                        severity="error",
                        message=(
                            "La numeración de [FUENTE N] no "
                            "es continua desde 1."
                        ),
                        location="FUENTES",
                    )
                )

        all_refs = {
            int(value)
            for value in re.findall(
                r"\[FUENTE (\d+)\]",
                content,
            )
        }

        invalid_refs = sorted(
            all_refs - blocks
        )

        if invalid_refs:
            issues.append(
                PromptValidationIssue(
                    code="unknown_source_reference",
                    severity="error",
                    message=(
                        "Se encontraron referencias a fuentes "
                        "inexistentes: "
                        + ", ".join(
                            map(str, invalid_refs)
                        )
                    ),
                    location="Documento completo",
                )
            )

        for code, pattern in self.FORBIDDEN_ACTIVE_PATTERNS:
            match = pattern.search(content)
            if match:
                issues.append(
                    PromptValidationIssue(
                        code=code,
                        severity="error",
                        message=(
                            "El expediente contiene una orden "
                            "incompatible con el modo cerrado."
                        ),
                        location=match.group(0),
                    )
                )

        if (
            "No preguntes qué debe hacerse"
            not in content
        ):
            issues.append(
                PromptValidationIssue(
                    code="missing_no_question_rule",
                    severity="warning",
                    message=(
                        "No se detectó la prohibición expresa "
                        "de pedir una nueva consigna."
                    ),
                    location="Bootstrap",
                )
            )

        if len(content.strip()) < 500:
            issues.append(
                PromptValidationIssue(
                    code="content_too_short",
                    severity="error",
                    message=(
                        "El expediente compilado es demasiado "
                        "breve para constituir un contexto válido."
                    ),
                    location="Documento completo",
                )
            )

        errors = [
            issue
            for issue in issues
            if issue.severity == "error"
        ]

        return PromptValidationResult(
            valid=not errors,
            issues=issues,
        )
