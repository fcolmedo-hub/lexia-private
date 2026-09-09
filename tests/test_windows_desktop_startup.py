from __future__ import annotations

import importlib.util
import hashlib
import io
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
            connection = sqlite3.connect(database)
            try:
                connection.execute(
                    "CREATE TABLE documents (path TEXT PRIMARY KEY, is_deleted INTEGER)"
                )
                connection.executemany(
                    "INSERT INTO documents(path,is_deleted) VALUES (?,?)",
                    [("active-a", 0), ("active-b", 0), ("deleted", 1)],
                )
                connection.commit()
            finally:
                # sqlite3.Connection.__exit__ no cierra la conexión. Windows
                # no permite borrar el archivo temporal mientras siga abierto.
                connection.close()

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

    def test_windows_launcher_injects_current_standards_assets(self) -> None:
        launcher = _load_launcher()
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            ui = root / "app" / "ui2"
            assets = ui / "assets"
            assets.mkdir(parents=True)
            for name in (
                "jurisprudence_search.js",
                "search_investigation_bridge.js",
                "windows_live_badge_cleanup.js",
                "app_runtime.js",
            ):
                (assets / name).write_text("", encoding="utf-8")
            navigator = ui / "navigator_3_3_4a.js"
            navigator.write_text("window.windowsNavigator=true;", encoding="utf-8")
            standards_ui = assets / "standards_ui.js"
            standards_nav = assets / "standards_nav_fix.js"
            standards_ui.write_text("window.windowsStandards=true;", encoding="utf-8")
            standards_nav.write_text("window.windowsStandardsNav=true;", encoding="utf-8")
            index = ui / "index.html"
            original = "<html><body></body></html>"
            index.write_text(original, encoding="utf-8")

            saved = launcher.ensure_ui_assets(root)
            patched = index.read_text(encoding="utf-8")
            ui_hash = hashlib.sha256(standards_ui.read_bytes()).hexdigest()[:12]
            nav_hash = hashlib.sha256(standards_nav.read_bytes()).hexdigest()[:12]

            self.assertEqual(saved, original)
            self.assertIn("window.LEXIA_STANDARDS_PORT=8515", patched)
            self.assertIn(f"standards_ui.js?v=standards-ui-{ui_hash}", patched)
            self.assertIn(f"standards_nav_fix.js?v=standards-nav-fix-{nav_hash}", patched)
            launcher.restore_ui_assets(root, saved)
            self.assertEqual(index.read_text(encoding="utf-8"), original)

    def test_windows_launcher_refreshes_file_menu_and_investigate_assets(self) -> None:
        launcher = _load_launcher()
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            ui = root / "app" / "ui2"
            assets = ui / "assets"
            assets.mkdir(parents=True)
            required = {
                "jurisprudence_search.js": "window.search=true;",
                "search_investigation_bridge.js": "window.investigate=true;",
                "windows_live_badge_cleanup.js": "",
                "app_runtime.js": "",
            }
            for name, content in required.items():
                (assets / name).write_text(content, encoding="utf-8")
            navigator = ui / "navigator_3_3_4a.js"
            navigator.write_text("window.fileMenu=true;", encoding="utf-8")
            index = ui / "index.html"
            original = (
                '<html><body>'
                '<script src="navigator_3_3_4a.js?v=old"></script>'
                '<script src="assets/jurisprudence_search.js?v=old"></script>'
                '</body></html>'
            )
            index.write_text(original, encoding="utf-8")

            saved = launcher.ensure_ui_assets(root)
            patched = index.read_text(encoding="utf-8")
            nav_hash = hashlib.sha256(navigator.read_bytes()).hexdigest()[:12]
            search = assets / "jurisprudence_search.js"
            search_hash = hashlib.sha256(search.read_bytes()).hexdigest()[:12]
            bridge = assets / "search_investigation_bridge.js"
            bridge_hash = hashlib.sha256(bridge.read_bytes()).hexdigest()[:12]

            self.assertEqual(saved, original)
            self.assertIn(
                f'navigator_3_3_4a.js?v=navigator-{nav_hash}', patched
            )
            self.assertIn(
                f'jurisprudence_search.js?v=jurisprudence-search-{search_hash}',
                patched,
            )
            bridge_tag = (
                '<script id="lexiaSearchInvestigationBridge" '
                f'src="assets/search_investigation_bridge.js?v=search-investigation-{bridge_hash}"></script>'
            )
            self.assertIn(bridge_tag, patched)
            self.assertLess(
                patched.index(bridge_tag),
                patched.index("assets/jurisprudence_search.js"),
            )

    def test_windows_launcher_starts_standards_api_with_expected_port(self) -> None:
        launcher = _load_launcher()
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            script = root / "app" / "ui2" / "standards_api.py"
            script.parent.mkdir(parents=True)
            script.write_text("", encoding="utf-8")
            py = root / ".venv" / "Scripts" / "python.exe"
            process = object()
            with patch.object(launcher.subprocess, "Popen", return_value=process) as popen:
                result = launcher.start_standards_api(
                    root, py, {"BASE": "1"}, 123, io.BytesIO()
                )

            self.assertIs(result, process)
            args, kwargs = popen.call_args
            self.assertEqual(args[0], [str(py), str(script)])
            self.assertEqual(kwargs["env"]["LEXIA_STANDARDS_PORT"], "8515")
            self.assertEqual(kwargs["creationflags"], 123)


if __name__ == "__main__":
    unittest.main()
