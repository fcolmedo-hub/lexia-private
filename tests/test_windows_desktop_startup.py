from __future__ import annotations

import base64
import importlib.util
import json
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

    def test_catalog_document_count_prefers_small_autosync_cache(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            runtime = root / "runtime"
            runtime.mkdir()
            (runtime / "lexia_catalog.sqlite3").write_bytes(b"not-opened")
            (runtime / "autosync_state.json").write_text(
                json.dumps({"documents_total": 86790}),
                encoding="utf-8",
            )

            launcher = _load_launcher()
            with patch.object(launcher, "log_startup") as log:
                total = launcher.catalog_document_count(root, timeout=0)

            self.assertEqual(total, 86790)
            self.assertIn("total en caché", log.call_args.args[0])

    def test_windows_runtime_injects_immediate_catalog_total_before_home_loader(self) -> None:
        launcher = _load_launcher()
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            ui = root / "app" / "ui2"
            assets = ui / "assets"
            assets.mkdir(parents=True)
            (ui / "index.html").write_text(
                '<html><body><script src="assets/jurisprudence_search.js"></script>'
                '<script src="assets/app_runtime.js"></script></body></html>',
                encoding="utf-8",
            )
            for name in (
                "jurisprudence_search.js",
                "search_investigation_bridge.js",
                "windows_live_badge_cleanup.js",
                "windows_search_results_polish.js",
                "app_runtime.js",
            ):
                (assets / name).write_text("// " + name, encoding="utf-8")
            (ui / "navigator_3_3_4a.js").write_text("// navigator", encoding="utf-8")

            original = launcher.ensure_ui_assets(root, expected_documents=86790)
            rendered = (ui / "index.html").read_text(encoding="utf-8")

            self.assertIsNotNone(original)
            self.assertIn("window.__lexiaWindowsFastStartupV1=true", rendered)
            self.assertIn("window.__lexiaWindowsStartupDocuments=86790", rendered)
            self.assertLess(
                rendered.index("lexiaWindowsFastHome"),
                rendered.index("assets/jurisprudence_search.js"),
            )

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

    def test_source_launcher_materializes_bundled_lexia_icon(self) -> None:
        launcher = _load_launcher()
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw) / "project"
            (root / "assets").mkdir(parents=True)
            icon_bytes = b"\x00\x00\x01\x00lexia-icon-test"
            (root / "assets" / "LexIA.ico.b64").write_text(
                base64.b64encode(icon_bytes).decode("ascii"), encoding="ascii"
            )
            appdata = Path(raw) / "appdata"
            with patch.object(launcher, "local_appdata", return_value=appdata):
                icon = launcher.prepare_window_icon(root)

            self.assertEqual(icon, appdata / "LexIA" / "LexIA.ico")
            self.assertEqual(icon.read_bytes(), icon_bytes)

    def test_pywebview_start_applies_runtime_icon_without_pyinstaller(self) -> None:
        source = LAUNCHER.read_text(encoding="utf-8")

        self.assertIn("def apply_window_icon(root: Path)", source)
        self.assertIn("user32.SendMessageW(hwnd, wm_seticon, icon_big, int(handle))", source)
        self.assertIn('if icon_path is not None and "icon" in parameters:', source)
        self.assertIn("webview.start(private_mode=False, icon=str(icon_path))", source)
        self.assertIn("start_desktop_webview(webview, root)", source)

    def test_desktop_webview_passes_materialized_icon_to_supported_pywebview(self) -> None:
        launcher = _load_launcher()

        class FakeWebview:
            call = None

            def start(self, private_mode=True, icon=None):
                self.call = {"private_mode": private_mode, "icon": icon}

        fake = FakeWebview()
        icon = Path("C:/LexIA/LexIA.ico")
        with (
            patch.object(launcher, "prepare_window_icon", return_value=icon),
            patch.object(launcher, "log_startup"),
        ):
            launcher.start_desktop_webview(fake, Path("C:/LexIA"))

        self.assertEqual(fake.call, {"private_mode": False, "icon": str(icon)})


if __name__ == "__main__":
    unittest.main()
