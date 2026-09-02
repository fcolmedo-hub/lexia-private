from __future__ import annotations

import importlib.util
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
LAUNCHER = ROOT / "app" / "ui2" / "windows_desktop.py"


def _load_launcher():
    spec = importlib.util.spec_from_file_location("lexia_windows_desktop_test", LAUNCHER)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class _RunningProcess:
    @staticmethod
    def poll():
        return None


class WindowsDesktopStartupTests(unittest.TestCase):
    def test_catalog_document_count_reads_existing_library(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            runtime = root / "runtime"
            runtime.mkdir()
            database = runtime / "lexia_catalog.sqlite3"
            with sqlite3.connect(database) as connection:
                connection.execute(
                    "CREATE TABLE documents (path TEXT PRIMARY KEY, is_deleted INTEGER)"
                )
                connection.executemany(
                    "INSERT INTO documents(path,is_deleted) VALUES (?,?)",
                    [("active-a", 0), ("active-b", 0), ("deleted", 1)],
                )

            launcher = _load_launcher()
            self.assertEqual(launcher.catalog_document_count(root, timeout=0.1), 2)

    def test_wait_qdrant_requires_healthy_http_payload(self) -> None:
        launcher = _load_launcher()
        replies = iter([
            None,
            {"status": "starting", "result": {}},
            {"status": "ok", "result": {"collections": []}},
        ])
        with (
            patch.object(
                launcher,
                "_http_json",
                side_effect=lambda *_args, **_kwargs: next(replies),
            ),
            patch.object(launcher.time, "sleep", return_value=None),
        ):
            self.assertTrue(launcher.wait_qdrant(1.0))

    def test_ui_wait_does_not_accept_transient_empty_catalog(self) -> None:
        launcher = _load_launcher()
        live_replies = iter([
            {"ok": True, "catalog": {"documents": 0}},
            {"ok": True, "catalog": {"documents": 85787}},
        ])

        def fake_http_json(url, timeout=1.0):
            if url.endswith("/api/live"):
                return next(live_replies)
            return {"ok": True}

        with (
            patch.object(launcher, "_http_json", side_effect=fake_http_json),
            patch.object(launcher, "log_startup"),
            patch.object(launcher.time, "sleep", return_value=None),
        ):
            launcher.wait_ui_ready(
                _RunningProcess(),
                expected_documents=85787,
                timeout=1.0,
            )

    def test_non_windows_mutex_is_a_noop(self) -> None:
        launcher = _load_launcher()
        if launcher.os.name != "nt":
            self.assertEqual(launcher.acquire_startup_mutex(), (True, None))


if __name__ == "__main__":
    unittest.main()
