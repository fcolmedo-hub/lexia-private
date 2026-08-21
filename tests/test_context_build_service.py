import time

from services.context_build_service import ContextBuildService


class FakeHistory:
    def __init__(self):
        self.saved = []

    def save(self, **kwargs):
        self.saved.append(kwargs)


class FakeBuilder:
    def __init__(self):
        self.saved = []

    def build_research_package(self, **kwargs):
        time.sleep(0.05)
        return {"query": kwargs["query"]}

    def save(self, package):
        self.saved.append(package)
        return ("context.txt",)


def test_context_job_runs_in_background_and_keeps_result():
    history = FakeHistory()
    builder = FakeBuilder()
    service = ContextBuildService(builder, history)

    job_id = service.start_job(
        query="consulta",
        facts="hechos",
        objective="Investigación jurídica",
        additional_instruction="",
        max_sources=10,
    )

    assert job_id
    assert service.running() is True

    deadline = time.time() + 2
    while service.running() and time.time() < deadline:
        time.sleep(0.01)

    state = service.state()
    assert state["phase"] == "completed"
    assert state["percentage"] == 100
    assert service.result() is not None
    assert service.result().package == {"query": "consulta"}
    assert len(history.saved) == 1


def test_context_job_rejects_second_concurrent_job():
    history = FakeHistory()
    builder = FakeBuilder()
    service = ContextBuildService(builder, history)

    service.start_job(
        query="primera",
        facts="",
        objective="Investigación jurídica",
        additional_instruction="",
        max_sources=10,
    )

    try:
        service.start_job(
            query="segunda",
            facts="",
            objective="Investigación jurídica",
            additional_instruction="",
            max_sources=10,
        )
    except RuntimeError:
        pass
    else:
        raise AssertionError("Debió impedir una segunda investigación concurrente.")
