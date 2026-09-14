from pathlib import Path
from types import SimpleNamespace

from ai.research_answer_service import ResearchAnswerService
from services.research_result_archive import ResearchResultArchive


class FakeClient:
    model = "gpt-test"

    def respond(self, **kwargs):
        assert "PAQUETE" in kwargs["user_input"]
        return SimpleNamespace(
            text="# Resultado\n\nAnálisis jurídico.",
            response_id="resp_123",
            input_tokens=100,
            output_tokens=40,
            total_tokens=140,
        )


def test_research_answer_uses_internal_package_without_exposing_it():
    answer = ResearchAnswerService(FakeClient()).answer("# PAQUETE")
    assert answer.text.startswith("# Resultado")
    assert answer.model == "gpt-test"
    assert answer.total_tokens == 140


def test_archive_persists_both_result_types(tmp_path: Path):
    path = tmp_path / "research_results.sqlite3"
    archive = ResearchResultArchive(path)
    research = archive.add(
        kind="research", query="Consulta tributaria", title="Resultado",
        result="Respuesta extensa", model="gpt-test", total_tokens=140,
        source_count=8, document_count=5,
    )
    study = archive.add(
        kind="file", query="Estudiar fallo.pdf", title="fallo.pdf",
        result="Estudio del fallo",
    )

    reopened = ResearchResultArchive(path)
    items = reopened.list()
    assert [item["kind"] for item in items] == ["file", "research"]
    assert "result" not in items[0]
    assert items[0]["preview"] == "Estudio del fallo"
    assert reopened.get(research["id"])["result"] == "Respuesta extensa"
    assert reopened.get(study["id"])["type_label"] == "Estudio de archivo"


def test_archive_searches_title_query_and_full_content_and_deletes(tmp_path: Path):
    archive = ResearchResultArchive(tmp_path / "research_results.sqlite3")
    first = archive.add(
        kind="research", query="Responsabilidad contractual",
        title="Daños por incumplimiento", result="Incluye lucro cesante.",
    )
    second = archive.add(
        kind="file", query="Estudiar sentencia.pdf",
        title="Sentencia comercial", result="Analiza una cláusula penal.",
    )

    assert [item["id"] for item in archive.search("DAÑOS")] == [first["id"]]
    assert [item["id"] for item in archive.search("contractual")] == [first["id"]]
    assert [item["id"] for item in archive.search("cláusula penal")] == [second["id"]]
    assert "result" not in archive.search("cláusula penal")[0]

    archive.delete(first["id"])
    assert [item["id"] for item in archive.list()] == [second["id"]]
    try:
        archive.delete(first["id"])
    except KeyError:
        pass
    else:
        raise AssertionError("Eliminar dos veces debía informar que el registro no existe")
