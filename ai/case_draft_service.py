from __future__ import annotations

import json
from typing import Any

from ai.chatgpt_message_builder import ChatGPTCaseMessageBuilder
from ai.openai_client import OpenAIClient, OpenAIClientError


class CaseDraftServiceError(RuntimeError):
    pass


class CaseDraftService:
    """Envía una rama de Casos al cliente OpenAI y valida la salida estructurada."""

    def __init__(self, client=None, message_builder=None):
        self.client = client or OpenAIClient()
        self.message_builder = message_builder or ChatGPTCaseMessageBuilder()

    def draft(
        self,
        *,
        case_name: str,
        branch_title: str,
        branch_material: str,
        case_metadata: dict[str, Any] | None = None,
        requested_document_type: str | None = None,
        drafting_instruction: str | None = None,
        max_output_tokens: int | None = None,
    ) -> dict[str, Any]:
        messages = self.message_builder.build(
            case_name=case_name,
            branch_title=branch_title,
            branch_material=branch_material,
            case_metadata=case_metadata,
            requested_document_type=requested_document_type,
            drafting_instruction=drafting_instruction,
        )

        try:
            answer = self.client.respond(
                instructions=messages.instructions,
                user_input=messages.user_input,
                max_output_tokens=max_output_tokens,
                response_format=messages.response_format,
            )
        except OpenAIClientError as error:
            raise CaseDraftServiceError(str(error)) from error

        try:
            payload = json.loads(answer.text)
        except (TypeError, json.JSONDecodeError) as error:
            raise CaseDraftServiceError(
                "La IA respondió con un formato de redacción inválido."
            ) from error

        if not isinstance(payload, dict):
            raise CaseDraftServiceError(
                "La IA respondió con un resultado de redacción inválido."
            )

        status = str(payload.get("status", "") or "").strip()
        if status not in {"ready", "needs_confirmation"}:
            raise CaseDraftServiceError(
                "La IA no indicó un estado válido para la redacción."
            )

        document_type = str(payload.get("document_type", "") or "").strip()
        represented_role = str(payload.get("represented_role", "") or "").strip()
        procedural_stage = str(payload.get("procedural_stage", "") or "").strip()
        draft_title = str(payload.get("draft_title", "") or "").strip()
        draft_markdown = str(payload.get("draft_markdown", "") or "").strip()
        missing = payload.get("missing_information") or []
        if not isinstance(missing, list):
            missing = [str(missing)]
        missing = [str(item).strip() for item in missing if str(item).strip()]

        try:
            confidence = max(0, min(100, int(payload.get("confidence", 0) or 0)))
        except (TypeError, ValueError):
            confidence = 0

        if status == "ready" and not draft_markdown:
            raise CaseDraftServiceError(
                "La IA indicó que el escrito estaba listo pero no devolvió texto."
            )
        if status == "needs_confirmation":
            draft_title = ""
            draft_markdown = ""

        return {
            "status": status,
            "document_type": document_type,
            "represented_role": represented_role,
            "procedural_stage": procedural_stage,
            "confidence": confidence,
            "missing_information": missing,
            "draft_title": draft_title,
            "draft_markdown": draft_markdown,
            "model": str(getattr(self.client, "model", "") or ""),
            "response_id": str(getattr(answer, "response_id", "") or ""),
            "usage": {
                "input_tokens": int(getattr(answer, "input_tokens", 0) or 0),
                "output_tokens": int(getattr(answer, "output_tokens", 0) or 0),
                "total_tokens": int(getattr(answer, "total_tokens", 0) or 0),
            },
        }
