from pathlib import Path
from types import SimpleNamespace

import pytest

from ai.case_draft_service import CaseDraftService, CaseDraftServiceError


ROOT = Path(__file__).resolve().parents[1]


class FakeClient:
    model = "fake-model"

    def __init__(self, text):
        self.text = text
        self.calls = []

    def respond(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(
            text=self.text,
            input_tokens=120,
            output_tokens=340,
            total_tokens=460,
            response_id="resp_test",
        )


def test_case_draft_service_sends_structured_prompt_to_client():
    client = FakeClient(
        '{"status":"ready","document_type":"contestación de demanda",'
        '"represented_role":"demandado","procedural_stage":"contestación",'
        '"confidence":96,"missing_information":[],"draft_title":"Contesta demanda",'
        '"draft_markdown":"# CONTESTA DEMANDA\\n\\nTexto final"}'
    )
    service = CaseDraftService(client=client)

    result = service.draft(
        case_name="Actor c/ Demandado",
        branch_title="Demanda",
        branch_material="CUESTIÓN\nFecha de ingreso...",
    )

    assert result["status"] == "ready"
    assert result["document_type"] == "contestación de demanda"
    assert result["draft_markdown"].startswith("# CONTESTA DEMANDA")
    assert result["usage"]["total_tokens"] == 460
    assert result["response_id"] == "resp_test"

    call = client.calls[0]
    assert "instructions" in call
    assert "user_input" in call
    assert call["response_format"]["name"] == "lexia_case_draft"


def test_case_draft_service_returns_confirmation_without_draft():
    client = FakeClient(
        '{"status":"needs_confirmation","document_type":"",'
        '"represented_role":"","procedural_stage":"","confidence":35,'
        '"missing_information":["Indicar qué parte representamos"],'
        '"draft_title":"No usar","draft_markdown":"No usar"}'
    )

    result = CaseDraftService(client=client).draft(
        case_name="Caso",
        branch_title="Rama",
        branch_material="Material ambiguo",
    )

    assert result["status"] == "needs_confirmation"
    assert result["missing_information"] == ["Indicar qué parte representamos"]
    assert result["draft_title"] == ""
    assert result["draft_markdown"] == ""


def test_case_draft_service_rejects_invalid_payload():
    client = FakeClient("respuesta no json")

    with pytest.raises(CaseDraftServiceError):
        CaseDraftService(client=client).draft(
            case_name="Caso",
            branch_title="Rama",
            branch_material="Material suficiente",
        )


def test_case_branch_ui_sends_material_to_case_draft_endpoint():
    ui = (ROOT / "app/ui2/assets/case_workspace.js").read_text(encoding="utf-8")
    server = (ROOT / "app/ui2/server.py").read_text(encoding="utf-8")

    assert "Enviar rama a la IA" in ui
    assert "buildBranchAiMaterial(root, chosen)" in ui
    assert "api('/api/cases/ai/draft'" in ui
    assert "details.open = true" in ui
    assert 'if path == "/api/cases/ai/draft":' in server
    assert "CaseDraftService().draft(" in server
    assert 'status="borrador"' in server
