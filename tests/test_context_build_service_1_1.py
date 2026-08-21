import time

from services.context_build_service import ContextBuildService


class FakeHistory:
    def save(self, **kwargs):
        return None


class FakeBuilder:
    def build_research_package(self, **kwargs):
        time.sleep(0.03)
        return {"query": kwargs["query"], "sources": [1, 2, 3]}

    def save(self, package):
        return ("Contexto.txt", "Mensaje.txt")


def wait(service):
    deadline = time.time() + 2
    while service.running() and time.time() < deadline:
        time.sleep(0.01)


def test_completed_result_remains_available_until_next_job():
    service = ContextBuildService(FakeBuilder(), FakeHistory())

    first = service.start_job(
        query="primera",
        facts="",
        objective="Investigación jurídica",
        additional_instruction="",
        max_sources=14,
    )
    wait(service)

    assert service.state()["phase"] == "completed"
    result1 = service.result()
    assert result1 is not None
    assert result1.job_id == first
    assert result1.package["sources"] == [1, 2, 3]

    # Leer state/result varias veces simula navegar y volver:
    assert service.state()["phase"] == "completed"
    assert service.result() is result1

    second = service.start_job(
        query="segunda",
        facts="",
        objective="Investigación jurídica",
        additional_instruction="",
        max_sources=14,
    )

    # Al iniciar una nueva búsqueda se descarta recién el resultado anterior.
    assert second != first
    assert service.result() is None
    wait(service)

    assert service.result() is not None
    assert service.result().job_id == second
