import json
import re
from typing import Any

from ai.openai_client import OpenAIAnswer, OpenAIClient


class CaseStructureError(ValueError):
    """Raised when an AI proposal cannot be traced to its source document."""


CASE_STRUCTURE_SCHEMA = {
    "type": "json_schema",
    "name": "lexia_case_structure",
    "strict": True,
    "schema": {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "issues": {
                "type": "array",
                "maxItems": 30,
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "title": {"type": "string"},
                        "adversary_blocks": {
                            "type": "array",
                            "items": {"$ref": "#/$defs/block"},
                        },
                        "own_blocks": {
                            "type": "array",
                            "items": {"$ref": "#/$defs/block"},
                        },
                    },
                    "required": ["title", "adversary_blocks", "own_blocks"],
                },
            }
        },
        "required": ["issues"],
        "$defs": {
            "block": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "content": {"type": "string"},
                    "quotes": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                },
                "required": ["content", "quotes"],
            }
        },
    },
}


class CaseStructureAnalyzer:
    INSTRUCTIONS = """
Sos un asistente de análisis jurídico documental para un abogado argentino.
Tu única función es proponer la estructura inicial de un caso a partir del
documento entregado.

REGLAS ESTRICTAS:
- Trabajá exclusivamente con el documento. No uses conocimiento externo.
- Identificá cuestiones jurídicas o fácticas controvertidas, no simples títulos
  formales ni datos administrativos aislados.
- Cada bloque del planteo de la contraparte debe incluir al menos una cita
  textual exacta del documento en `quotes`.
- Las citas deben copiarse literalmente, sin corregir, resumir ni completar.
- `content` es un enunciado breve y fiel del planteo que expresa esa cita.
- No inventes hechos, normas, jurisprudencia, fechas, pretensiones ni defensas.
- No dupliques cuestiones equivalentes.
- Si se solicita nuestra postura, proponela sólo como borrador y únicamente a
  partir de contradicciones, límites o elementos que surjan del documento. No
  agregues derecho ni hechos externos. Sus citas pueden quedar vacías.
- Si nuestra postura no fue solicitada, `own_blocks` debe ser siempre [].
- Devolvé únicamente el objeto JSON solicitado.
"""

    def __init__(self, client: OpenAIClient | None = None, max_chars: int = 500_000):
        self.client = client or OpenAIClient()
        self.max_chars = max(20_000, int(max_chars))

    def analyze(self, document_name: str, document_text: str, include_own: bool = False) -> dict:
        package = self.manual_package(document_name, document_text, include_own)
        supplied = package["source_text"]
        answer = self.client.respond(
            self.INSTRUCTIONS,
            package["user_input"],
            max_output_tokens=20_000,
            response_format=CASE_STRUCTURE_SCHEMA,
        )
        raw = self._parse_json(answer.text)
        proposal = self.validate_proposal(raw, supplied, include_own=include_own)
        return {
            "proposal": proposal,
            "model": self.client.model,
            "response_id": answer.response_id,
            "usage": {
                "input_tokens": answer.input_tokens,
                "output_tokens": answer.output_tokens,
                "total_tokens": answer.total_tokens,
            },
            "document_truncated": package["document_truncated"],
            "analyzed_chars": len(supplied),
        }

    def manual_package(self, document_name: str, document_text: str, include_own: bool = False) -> dict:
        text = str(document_text or "").strip()
        if not text:
            raise CaseStructureError("LexIA no tiene texto indexado para analizar este documento.")
        truncated = len(text) > self.max_chars
        supplied = text[: self.max_chars]
        user_input = (
            f"DOCUMENTO: {document_name}\n"
            f"PROPONER NUESTRA POSTURA: {'SÍ' if include_own else 'NO'}\n"
            f"TEXTO COMPLETO ENVIADO: {'NO, recortado por límite de seguridad' if truncated else 'SÍ'}\n\n"
            "TEXTO DEL DOCUMENTO:\n" + supplied
        )
        prompt = (
            "# LEXIA — ESTRUCTURA INICIAL DEL CASO\n\n"
            + self.INSTRUCTIONS.strip()
            + "\n\nFORMATO JSON OBLIGATORIO:\n"
            + json.dumps(CASE_STRUCTURE_SCHEMA["schema"], ensure_ascii=False, indent=2)
            + "\n\n"
            + user_input
        )
        return {
            "prompt": prompt,
            "source_text": supplied,
            "user_input": user_input,
            "document_truncated": truncated,
        }

    @classmethod
    def parse_and_validate(cls, raw_text: str, source_text: str, include_own: bool = True) -> dict:
        return cls.validate_proposal(cls._parse_json(raw_text), source_text, include_own=include_own)

    @staticmethod
    def _parse_json(raw_text: str) -> dict:
        text = str(raw_text or "").strip()
        if text.startswith("```"):
            text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
            text = re.sub(r"\s*```$", "", text)
        try:
            value = json.loads(text)
        except json.JSONDecodeError as exc:
            raise CaseStructureError("La IA no devolvió una estructura JSON válida.") from exc
        if not isinstance(value, dict):
            raise CaseStructureError("La respuesta de la IA no contiene una estructura de cuestiones.")
        return value

    @classmethod
    def validate_proposal(cls, payload: dict, source_text: str, include_own: bool = True) -> dict:
        if not isinstance(payload, dict) or not isinstance(payload.get("issues"), list):
            raise CaseStructureError("La propuesta no contiene una lista válida de cuestiones.")
        source = str(source_text or "")
        issues = []
        for issue_number, raw_issue in enumerate(payload["issues"][:30], start=1):
            if not isinstance(raw_issue, dict):
                continue
            title = str(raw_issue.get("title", "") or "").strip()[:240]
            if not title:
                continue
            adversary = cls._validate_blocks(
                raw_issue.get("adversary_blocks", raw_issue.get("blocks", {}).get("contraparte", [])),
                source,
                require_quote=True,
                context=f"cuestión {issue_number}",
            )
            if not adversary:
                raise CaseStructureError(
                    f"La cuestión “{title}” no contiene un planteo respaldado por una cita literal."
                )
            own_raw = raw_issue.get("own_blocks", raw_issue.get("blocks", {}).get("propia", []))
            own = cls._validate_blocks(own_raw, source, require_quote=False, context=f"cuestión {issue_number}") if include_own else []
            issues.append({
                "title": title,
                "blocks": {"contraparte": adversary, "propia": own},
            })
        if not issues:
            raise CaseStructureError("La IA no detectó ninguna cuestión respaldada por el documento.")
        return {"issues": issues}

    @classmethod
    def _validate_blocks(cls, values: Any, source: str, *, require_quote: bool, context: str) -> list[dict]:
        if not isinstance(values, list):
            return []
        output = []
        for raw_block in values[:40]:
            if not isinstance(raw_block, dict):
                continue
            content = str(raw_block.get("content", "") or "").strip()[:8_000]
            if not content:
                continue
            raw_quotes = raw_block.get("quotes")
            if raw_quotes is None:
                raw_quotes = [item.get("selected_text", "") for item in raw_block.get("highlights", []) if isinstance(item, dict)]
            highlights = []
            for quote in raw_quotes if isinstance(raw_quotes, list) else []:
                located = cls.locate_quote(source, str(quote or ""))
                if located and not any(item["start_char"] == located["start_char"] and item["end_char"] == located["end_char"] for item in highlights):
                    highlights.append(located)
            if require_quote and not highlights:
                raise CaseStructureError(
                    f"La IA propuso un bloque de la {context} cuya cita no aparece literalmente en el documento."
                )
            output.append({"content": content, "highlights": highlights})
        return output

    @staticmethod
    def locate_quote(source_text: str, quote_text: str) -> dict | None:
        source, quote = str(source_text or ""), str(quote_text or "").strip()
        if not quote:
            return None
        start = source.find(quote)
        if start < 0:
            words = re.findall(r"\S+", quote)
            if not words:
                return None
            pattern = r"\s+".join(re.escape(word) for word in words)
            match = re.search(pattern, source)
            if match is None:
                return None
            start, end = match.span()
        else:
            end = start + len(quote)
        return {
            "selected_text": source[start:end],
            "start_char": start,
            "end_char": end,
        }
