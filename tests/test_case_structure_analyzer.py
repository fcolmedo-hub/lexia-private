import json

import pytest

from ai.case_structure_analyzer import CaseStructureAnalyzer, CaseStructureError
from ai.openai_client import OpenAIAnswer
from storage.case_repository import CaseRepository


class FakeClient:
    model = "test-model"

    def __init__(self, payload):
        self.payload = payload

    def respond(self, instructions, user_input, max_output_tokens=None, response_format=None):
        assert response_format["type"] == "json_schema"
        return OpenAIAnswer(json.dumps(self.payload), 100, 40, 140, "response-test")


def test_analyzer_creates_traceable_preview_and_leaves_own_side_off():
    source = "El actor afirma que ingresó el 1 de noviembre de 2022.\nLa demandada lo niega."
    payload = {
        "issues": [{
            "title": "Fecha de ingreso",
            "adversary_blocks": [{
                "content": "El actor denuncia ingreso el 1/11/2022.",
                "quotes": ["El actor afirma que ingresó el 1 de noviembre de 2022."],
            }],
            "own_blocks": [{"content": "Borrador propio", "quotes": []}],
        }]
    }
    result = CaseStructureAnalyzer(FakeClient(payload)).analyze("demanda.pdf", source, False)
    issue = result["proposal"]["issues"][0]
    assert issue["blocks"]["propia"] == []
    assert issue["blocks"]["contraparte"][0]["highlights"][0]["selected_text"].startswith("El actor")


def test_analyzer_rejects_non_literal_adversary_quote():
    payload = {
        "issues": [{
            "title": "Cuestión inventada",
            "adversary_blocks": [{"content": "Contenido", "quotes": ["Esto no existe"]}],
            "own_blocks": [],
        }]
    }
    with pytest.raises(CaseStructureError, match="no aparece literalmente"):
        CaseStructureAnalyzer(FakeClient(payload)).analyze("demanda.pdf", "Texto real del documento", False)


def test_manual_package_and_response_validation_need_no_api():
    analyzer = CaseStructureAnalyzer(FakeClient({}))
    source = "La actora reclama diferencias salariales desde enero de 2023."
    package = analyzer.manual_package("demanda.pdf", source, include_own=False)
    assert "LEXIA — ESTRUCTURA INICIAL DEL CASO" in package["prompt"]
    assert source in package["prompt"]
    response = json.dumps({"issues": [{
        "title": "Diferencias salariales",
        "adversary_blocks": [{
            "content": "La actora reclama diferencias desde enero de 2023.",
            "quotes": ["La actora reclama diferencias salariales desde enero de 2023."],
        }],
        "own_blocks": [],
    }]})
    proposal = analyzer.parse_and_validate(response, source, include_own=False)
    assert proposal["issues"][0]["blocks"]["contraparte"][0]["highlights"]


def test_repository_applies_ai_structure_atomically(tmp_path):
    repository = CaseRepository(tmp_path / "cases.sqlite3")
    case_id = repository.create_case("Caso de prueba")
    document_id = repository.link_document(
        case_id,
        document_name="demanda.pdf",
        document_path=str(tmp_path / "demanda.pdf"),
        category="Escritos",
    )
    root_id = repository.add_node(
        case_id,
        node_kind="hito",
        title="Demanda",
        primary_document_id=document_id,
    )
    created = repository.apply_ai_structure(case_id, root_id, document_id, [{
        "title": "Fecha de ingreso",
        "blocks": {
            "contraparte": [{
                "content": "El actor denuncia otra fecha.",
                "highlights": [{
                    "selected_text": "Ingresó el día 1/11/2022",
                    "page_start": 2,
                    "page_end": 2,
                    "anchor_data": '{"origin":"ai_structure"}',
                }],
            }],
            "propia": [],
        },
    }])
    assert len(created) == 1
    question = repository.case_snapshot(case_id)["nodes"][0]["children"][0]
    assert question["title"] == "Fecha de ingreso"
    assert question["blocks"]["contraparte"][0]["title"] == "Borrador IA"
    assert question["blocks"]["contraparte"][0]["highlights"][0]["page_start"] == 2
