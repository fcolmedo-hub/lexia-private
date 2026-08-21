from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class PromptValidationIssue:
    code: str
    severity: str
    message: str
    location: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "severity": self.severity,
            "message": self.message,
            "location": self.location,
        }


@dataclass(slots=True)
class PromptValidationResult:
    valid: bool
    issues: list[PromptValidationIssue] = field(
        default_factory=list
    )

    @property
    def errors(self) -> list[PromptValidationIssue]:
        return [
            issue
            for issue in self.issues
            if issue.severity == "error"
        ]

    @property
    def warnings(self) -> list[PromptValidationIssue]:
        return [
            issue
            for issue in self.issues
            if issue.severity == "warning"
        ]

    def to_dict(self) -> dict[str, Any]:
        return {
            "valid": self.valid,
            "issues": [
                issue.to_dict()
                for issue in self.issues
            ],
        }


@dataclass(slots=True)
class PromptCompilationResult:
    content: str
    target: str
    protocol_version: str
    validation: PromptValidationResult
    original_character_count: int
    compiled_character_count: int
    source_count: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "target": self.target,
            "protocol_version": (
                self.protocol_version
            ),
            "original_character_count": (
                self.original_character_count
            ),
            "compiled_character_count": (
                self.compiled_character_count
            ),
            "source_count": self.source_count,
            "validation": (
                self.validation.to_dict()
            ),
        }
