import json
from argparse import Namespace

from tools.procesar_estandares_batch_v5 import SCHEMA, cmd_submit
from tools.validar_estandares_v5 import validate_result


def document():
    source = "Cámara de Apelaciones en lo Civil y Comercial de Santa Fe, Sala I. Santa Fe, 6 de agosto de 2013. Expte. 123/2013."
    return {"fragments": [{
        "chunk_id": "C0001", "text": source, "page_start": 1,
        "units": [{"unit_id": "C0001-U001", "unit_index": 1, "chunk_id": "C0001",
                   "start_offset": 0, "end_offset": len(source), "text": source}],
    }]}


def test_metadata_requires_literal_source_and_normalizes_date():
    response = {"document_metadata": {
        "court": {"value": "Cámara de Apelaciones en lo Civil y Comercial de Santa Fe", "unit_ids": ["C0001-U001"]},
        "chamber": {"value": "Sala I", "unit_ids": ["C0001-U001"]},
        "judgment_date": {"value": "6 de agosto de 2013", "unit_ids": ["C0001-U001"]},
        "case_number": {"value": "123/2013", "unit_ids": ["C0001-U001"]},
    }, "standards": []}
    result = validate_result(document(), json.dumps(response))
    assert result["document_metadata"]["judgment_date"] == "2013-08-06"
    assert result["document_metadata"]["chamber"] == "Sala I"
    assert result["document_metadata_evidence"]["court"]["unit_ids"] == ["C0001-U001"]
    assert result["standards"] == []
    assert not result["document_metadata_issues"]


def test_unsupported_or_unsubstantiated_metadata_stays_out_of_dictionary():
    response = {"document_metadata": {
        "court": {"value": "Juzgado Federal de Mendoza", "unit_ids": ["C0001-U001"]},
        "chamber": {"value": None, "unit_ids": []},
        "judgment_date": {"value": "6 de agosto de 2013", "unit_ids": ["desconocido"]},
        "case_number": {"value": None, "unit_ids": []},
    }, "standards": []}
    result = validate_result(document(), json.dumps(response))
    assert result["document_metadata"] == {}
    assert {issue["field"] for issue in result["document_metadata_issues"]} == {"court", "judgment_date"}
    assert "document_metadata" in SCHEMA["required"]


def test_resuming_recorded_batch_does_not_call_api(tmp_path, monkeypatch):
    (tmp_path / "batch_state.json").write_text('{"batch_id":"batch_existing"}', encoding="utf-8")
    monkeypatch.setattr("tools.procesar_estandares_batch_v5.require_sdk", lambda: (_ for _ in ()).throw(AssertionError("API called")))
    assert cmd_submit(Namespace(workdir=tmp_path)) == 0
