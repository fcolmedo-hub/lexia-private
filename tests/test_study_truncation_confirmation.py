import json
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Thread
from time import monotonic, sleep
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from http.server import ThreadingHTTPServer

from ai.context_package_builder import ContextPackage
from services import ui2_delete_bridge as bridge


class FakeBuilder:
    def __init__(self, available, included):
        self.available = available
        self.included = included
        self.calls = 0
        self.selection = None

    def build_documents_package(self, **_kwargs):
        self.calls += 1
        return ContextPackage(
            title="Fallo", content="Contenido truncado", sources=[],
            created_at="", character_count=18, objective="", query="", facts="",
            interpretation=(
                {"study_selection": self.selection} if self.selection else
                {"source_lengths": [{
                    "document": "fallo.pdf", "available": self.available, "included": self.included,
                }]}
            ),
            document_count=1, selected_count=1,
        )

    def save(self, _package):
        return {}


class StudyConfirmationTest(TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.source = root / "fallo.pdf"
        self.source.write_text("Fallo", encoding="utf-8")
        self.builder = FakeBuilder(240000, 200000)
        self.sent = []

        def fake_answer(_service, _package):
            self.sent.append(_package)
            return SimpleNamespace(
                text="Resultado", model="test", reasoning_effort="medium",
                prompt_mode="test", response_id="id",
                input_tokens=10, output_tokens=5, total_tokens=15,
            )

        settings = SimpleNamespace(runtime_path=root, library_path=root)
        self.settings_patch = patch.object(bridge, "SETTINGS", settings)
        self.answer_patch = patch.object(bridge.ResearchAnswerService, "answer", fake_answer)
        self.settings_patch.start()
        self.answer_patch.start()
        self.addCleanup(self.settings_patch.stop)
        self.addCleanup(self.answer_patch.stop)
        handler = bridge._handler_class(SimpleNamespace(context_builder=self.builder), "test-token")
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        self.addCleanup(self.server.server_close)
        self.thread = Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self.server.shutdown)
        self.url = f"http://127.0.0.1:{self.server.server_address[1]}"

    def request(self, path, payload=None):
        raw = None if payload is None else json.dumps(payload).encode("utf-8")
        request = Request(
            self.url + path, data=raw,
            headers={"X-LexIA-Delete-Token": "test-token", "Content-Type": "application/json"},
        )
        with urlopen(request, timeout=2) as response:
            return json.load(response)

    def phase(self, expected):
        deadline = monotonic() + 2
        while monotonic() < deadline:
            state = self.request("/api/study-status")["state"]
            if state["phase"] == expected:
                return state
            sleep(0.01)
        self.fail(f"No se alcanzó {expected}; último estado: {state}")

    def test_truncated_study_waits_for_explicit_confirmation(self):
        self.request("/api/study-start", {"path": str(self.source), "document_type": "Fallo judicial"})
        state = self.phase("awaiting_confirmation")
        self.assertEqual(state["truncation"], {"available": 240000, "included": 200000, "omitted": 40000})
        self.assertEqual(self.sent, [])
        self.request("/api/study-start", {"confirm_job_id": state["job_id"]})
        self.phase("completed")
        self.assertEqual(len(self.sent), 1)
        self.assertEqual(self.builder.calls, 1)
        with self.assertRaises(HTTPError):
            self.request("/api/study-start", {"confirm_job_id": state["job_id"]})
        self.assertEqual(len(self.sent), 1)

    def test_cancellation_never_calls_api(self):
        self.request("/api/study-start", {"path": str(self.source)})
        state = self.phase("awaiting_confirmation")
        self.request("/api/study-start", {"cancel_job_id": state["job_id"]})
        self.assertEqual(self.phase("idle")["truncation"], None)
        self.assertEqual(self.sent, [])

    def test_complete_document_runs_without_confirmation(self):
        self.builder.available = 180000
        self.builder.included = 180000
        self.request("/api/study-start", {"path": str(self.source)})
        self.phase("completed")
        self.assertEqual(len(self.sent), 1)

    def test_thematic_study_waits_even_without_character_truncation(self):
        self.builder.selection = {
            "kind": "thematic", "regions_found": 5, "regions_included": 3,
            "included_characters": 12000, "cut_by_budget": False,
        }
        self.request("/api/study-start", {"path": str(self.source), "document_type": "Doctrina"})
        state = self.phase("awaiting_confirmation")
        self.assertEqual(state["selection"]["regions_included"], 3)
        self.assertIsNone(state["truncation"])
        self.assertEqual(self.sent, [])
        self.request("/api/study-start", {"confirm_job_id": state["job_id"]})
        self.phase("completed")
        self.assertEqual(len(self.sent), 1)
