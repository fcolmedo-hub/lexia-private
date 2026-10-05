import contextlib
import importlib.util
import io
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import time
import types
import unittest
from unittest.mock import Mock, patch
import zipfile


def module(name, filename):
    spec = importlib.util.spec_from_file_location(name, Path(__file__).parents[1] / "scripts" / filename)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


cleanup = module("compact", "compact_windows_historical_backups.py")
guard = vars(module("guard", "clean_windows_generated_files.py")).copy()
guard["check_stopped"] = lambda root: []


class HistoricalCleanupTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def database(self, relative="runtime/lexia_catalog.sqlite3", wal=False):
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(path)
        if wal:
            connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("CREATE TABLE documents (path TEXT PRIMARY KEY, text TEXT)")
        connection.execute("INSERT INTO documents VALUES ('current.pdf', 'current text')")
        connection.commit()
        if wal:
            self.addCleanup(connection.close)
        else:
            connection.close()
        return path

    def archive(self, entries=None):
        path = self.root / cleanup.BASELINE / "codigo_y_configuracion.zip"
        path.parent.mkdir(parents=True, exist_ok=True)
        entries = entries or {
            "runtime/lexia_catalog.sqlite3": b"historical database",
            cleanup.SEED + "/lexia_catalog.sqlite3": b"seed database",
            "runtime/experiments/lexia_document_fts_test.sqlite3": b"rebuildable test database",
            "exports/analysis.docx": b"important paid analysis",
            "Rejected Documents/original.pdf": b"original rejected document",
            "app/ui2/index.html": b"historical source",
            "runtime/knowledge.sqlite3": b"keep historical knowledge",
            cleanup.SEED + "/jurisprudence_analyses.sqlite3": b"keep unique legacy results",
        }
        with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for name, content in entries.items():
                archive.writestr(name, content)
            archive.comment = b"historical archive comment"
        return path, entries

    def repo(self):
        subprocess.run(["git", "init", "-q", str(self.root)], check=True)
        (self.root / ".gitignore").write_text("runtime/\nbackups/\nruntime_seed_*/\ndata_test/\n.env\n.lexia_windows_app/\n")
        (self.root / "app/ui2").mkdir(parents=True)
        (self.root / "app/ui2/index.html").write_text("local Windows customization")
        subprocess.run(["git", "-C", str(self.root), "add", ".gitignore", "app"], check=True)
        subprocess.run(["git", "-C", str(self.root), "-c", "user.name=Test", "-c", "user.email=test@example.org", "commit", "-qm", "fixture"], check=True)
        (self.root / ".env").write_text("LOCAL_TEST_SETTING=preserve")
        (self.root / ".lexia_windows_app/LexIA").mkdir(parents=True)
        (self.root / ".lexia_windows_app/LexIA/LexIA.exe").write_bytes(b"fast startup executable")

    def run_main(self):
        settings = types.SimpleNamespace(runtime_path=self.root / "runtime", catalog_path=self.root / "runtime/lexia_catalog.sqlite3", library_path=self.root / "data_test")
        settings.__dataclass_fields__ = {name: None for name in ("runtime_path", "catalog_path", "library_path")}
        with patch.object(cleanup, "load_guard", return_value=guard), \
                patch.object(sys, "platform", "win32"), \
                patch.object(sys, "argv", ["cleanup.py", "--root", str(self.root), "--apply"]), \
                patch.object(sys, "path", sys.path[:]), \
                patch.dict(sys.modules, {"config.settings": types.SimpleNamespace(SETTINGS=settings)}), \
                contextlib.redirect_stdout(io.StringIO()):
            cleanup.main()

    def test_compaction_preserves_documents_source_unique_databases_and_comment(self):
        path, entries = self.archive()
        _, retired = cleanup.compact_archive(path)
        self.assertEqual(len(retired), 3)
        with zipfile.ZipFile(path) as archive:
            self.assertEqual(archive.comment, b"historical archive comment")
            self.assertIsNone(archive.testzip())
            self.assertEqual(set(archive.namelist()), {name for name in entries if not cleanup.dropped(name)})
            for name, content in entries.items():
                if not cleanup.dropped(name):
                    self.assertEqual(archive.read(name), content)

    def test_no_retired_entries_does_not_rewrite_archive(self):
        path, _ = self.archive({"exports/analysis.docx": b"keep"})
        old = path.read_bytes()
        self.assertEqual(cleanup.compact_archive(path), (0, []))
        self.assertEqual(path.read_bytes(), old)

    def test_changed_original_archive_is_not_replaced(self):
        path, _ = self.archive()
        original = path.read_bytes()
        real_fingerprint = cleanup.fingerprint
        calls = 0
        def changed(value):
            nonlocal calls
            calls += 1
            result = real_fingerprint(value)
            return result if calls == 1 else [result[0], result[1] + 1]
        with patch.object(cleanup, "fingerprint", side_effect=changed):
            with self.assertRaises(ValueError):
                cleanup.compact_archive(path)
        self.assertEqual(path.read_bytes(), original)
        self.assertFalse(list(path.parent.glob(".lexia-compact-*")))

    def test_atomic_replacement_failure_preserves_original(self):
        path, _ = self.archive()
        original = path.read_bytes()
        with patch.object(Path, "replace", side_effect=PermissionError("locked")):
            with self.assertRaises(PermissionError):
                cleanup.compact_archive(path)
        self.assertEqual(path.read_bytes(), original)
        self.assertFalse(list(path.parent.glob(".lexia-compact-*")))

    def test_wal_database_is_backed_up_consistently_without_changing_original(self):
        source = self.database(wal=True)
        before = source.read_bytes()
        target = self.root / "verified/catalog.sqlite3"
        result = cleanup.snapshot_database(source, target)
        self.assertEqual(result, cleanup.digest(target))
        with sqlite3.connect(target) as connection:
            self.assertEqual(connection.execute("SELECT text FROM documents").fetchone()[0], "current text")
        self.assertEqual(source.read_bytes(), before)

    def test_existing_backup_file_is_not_overwritten(self):
        source = self.database()
        target = self.root / "existing.sqlite3"
        target.write_bytes(b"existing backup")
        with self.assertRaises(ValueError):
            cleanup.snapshot_database(source, target)
        self.assertEqual(target.read_bytes(), b"existing backup")

    def test_corrupt_retained_zip_entry_preserves_original_and_old_catalog(self):
        path, _ = self.archive({"runtime/lexia_catalog.sqlite3": b"retire", "exports/analysis.docx": b"keep legal content"})
        with zipfile.ZipFile(path) as archive:
            entry = archive.getinfo("exports/analysis.docx")
        data = bytearray(path.read_bytes())
        name_size = int.from_bytes(data[entry.header_offset + 26:entry.header_offset + 28], "little")
        extra_size = int.from_bytes(data[entry.header_offset + 28:entry.header_offset + 30], "little")
        payload_offset = entry.header_offset + 30 + name_size + extra_size
        data[payload_offset] ^= 255
        path.write_bytes(data)
        before = path.read_bytes()
        with self.assertRaises(Exception):
            cleanup.compact_archive(path)
        self.assertEqual(path.read_bytes(), before)
        self.assertFalse(list(path.parent.glob(".lexia-compact-*")))

    def test_empty_catalog_blocks_retirement(self):
        source = self.database()
        with sqlite3.connect(source) as connection:
            connection.execute("DELETE FROM documents")
        with self.assertRaisesRegex(ValueError, "conteo"):
            cleanup.snapshot_database(source, self.root / "backup/catalog.sqlite3")

    def test_recovery_backup_is_verified_and_reused(self):
        self.repo()
        source = self.database()
        code = cleanup.source_files(self.root, guard)
        first, size, created = cleanup.recovery_backup(self.root, [source], code, guard)
        self.assertTrue(created)
        self.assertGreater(size, 0)
        with zipfile.ZipFile(first / "local_code_and_configuration.zip") as archive:
            self.assertEqual(archive.read(".env"), b"LOCAL_TEST_SETTING=preserve")
            self.assertEqual(archive.read(".lexia_windows_app/LexIA/LexIA.exe"), b"fast startup executable")
        second, _, created = cleanup.recovery_backup(self.root, [source], code, guard)
        self.assertFalse(created)
        self.assertEqual(first, second)

    def test_failed_database_backup_preserves_old_files_and_removes_own_staging(self):
        self.repo()
        source = self.database()
        (self.root / "backups").mkdir()
        old, _ = self.archive()
        original = old.read_bytes()
        with patch.object(cleanup, "run_snapshot_worker", side_effect=ValueError("invalid database")):
            with self.assertRaises(ValueError):
                cleanup.recovery_backup(self.root, [source], cleanup.source_files(self.root, guard), guard)
        self.assertEqual(old.read_bytes(), original)
        self.assertFalse(list((self.root / "backups").glob(".lexia-cleanup-current-*")))

    def test_local_operational_reference_blocks_retirement(self):
        folder = self.root / "app"
        folder.mkdir()
        (folder / "custom.py").write_text("folder = '" + cleanup.SEED + "'")
        with self.assertRaises(ValueError):
            cleanup.check_local_references(self.root, guard)

    def test_exact_archive_names_only_and_windows_path_variants(self):
        self.assertTrue(cleanup.dropped(r"LexIA_2.3_DEV\runtime\lexia_catalog.sqlite3"))
        self.assertTrue(cleanup.dropped("runtime/lexia_catalog.sqlite3-wal"))
        self.assertFalse(cleanup.dropped("exports/lexia_catalog.sqlite3"))
        self.assertFalse(cleanup.dropped("runtime/lexia_catalog.sqlite3.extra"))
        self.assertFalse(cleanup.dropped("../runtime/lexia_catalog.sqlite3"))
        self.assertFalse(cleanup.dropped("runtime/jurisprudence_analyses.sqlite3"))

    def test_complete_cleanup_preserves_live_data_qdrant_documents_and_startup(self):
        self.repo()
        live = self.database()
        live_bytes = live.read_bytes()
        old_paths = [self.database(name + suffix) for name, suffix in (
            (cleanup.BASELINE, "/runtime_sqlite/lexia_catalog.sqlite3"),
            (cleanup.MILESTONE, "/databases/runtime/lexia_catalog.sqlite3"),
            (cleanup.SEED, "/lexia_catalog.sqlite3"),
        )]
        archive, entries = self.archive()
        qdrant = self.root / cleanup.MILESTONE / "qdrant/important.snapshot"
        qdrant.parent.mkdir(parents=True)
        qdrant.write_bytes(b"unique vector snapshot")
        original = self.root / "data_test/original.pdf"
        original.parent.mkdir()
        original.write_bytes(b"original library document")
        self.run_main()
        self.assertEqual(live.read_bytes(), live_bytes)
        self.assertEqual(qdrant.read_bytes(), b"unique vector snapshot")
        self.assertEqual(original.read_bytes(), b"original library document")
        self.assertTrue(all(not path.exists() for path in old_paths))
        self.assertTrue((self.root / ".lexia_windows_app/LexIA/LexIA.exe").exists())
        with zipfile.ZipFile(archive) as package:
            self.assertEqual(package.read("exports/analysis.docx"), entries["exports/analysis.docx"])
        self.assertEqual(len(list((self.root / "backups").glob("lexia-cleanup-current-*"))), 1)
        self.run_main()
        self.assertEqual(len(list((self.root / "backups").glob("lexia-cleanup-current-*"))), 1)

    def test_busy_backup_has_bounded_idle_wait(self):
        times = iter([0, 1, 61])
        progress = cleanup.BackupProgress("catalog", idle_seconds=60, clock=lambda: next(times))
        progress(sqlite3.SQLITE_BUSY, 0, 0)
        with self.assertRaisesRegex(TimeoutError, "sin avanzar"):
            progress(sqlite3.SQLITE_BUSY, 0, 0)

    def test_advancing_backup_reports_progress(self):
        times = iter([0, 1, 70])
        progress = cleanup.BackupProgress("catalog", clock=lambda: next(times))
        with contextlib.redirect_stdout(io.StringIO()) as output:
            progress(sqlite3.SQLITE_OK, 100, 200)
            progress(sqlite3.SQLITE_DONE, 0, 200)
        self.assertIn("50.0%", output.getvalue())
        self.assertIn("100.0%", output.getvalue())

    def test_backup_has_total_deadline(self):
        times = iter([0, 601])
        progress = cleanup.BackupProgress("catalog", clock=lambda: next(times))
        with self.assertRaisesRegex(TimeoutError, "supero"):
            progress(sqlite3.SQLITE_DONE, 0, 200)

    def test_integrity_query_deadline_interrupts_and_removes_handler(self):
        times = iter([0, 2])
        with sqlite3.connect(":memory:") as connection:
            with self.assertRaisesRegex(TimeoutError, "supero"):
                cleanup.checked_query(connection,
                    "WITH RECURSIVE n(x) AS (VALUES(1) UNION ALL SELECT x+1 FROM n WHERE x<100000) SELECT SUM(x) FROM n",
                    "Integrity", max_seconds=1, clock=lambda: next(times))
            self.assertEqual(connection.execute("SELECT 1").fetchone(), (1,))

    def test_real_worker_copies_and_verifies_database(self):
        source = self.database()
        target = self.root / "backup/catalog.sqlite3"
        result = cleanup.run_snapshot_worker(source, target, stdout=subprocess.DEVNULL)
        self.assertEqual(result, cleanup.digest(target))
        self.assertTrue(target.with_name(target.name + ".verified.json").exists())

    def test_real_locked_database_times_out_without_modifying_original(self):
        source = self.database()
        before = source.read_bytes()
        with sqlite3.connect(source) as locker:
            locker.execute("BEGIN EXCLUSIVE")
            started = time.monotonic()
            with self.assertRaisesRegex(TimeoutError, "supero"):
                cleanup.run_snapshot_worker(source, self.root / "backup/catalog.sqlite3", max_seconds=1, stdout=subprocess.DEVNULL)
            self.assertLess(time.monotonic() - started, 5)
            self.assertEqual(source.read_bytes(), before)

    def test_cancellation_stops_only_the_owned_worker(self):
        source = self.database()
        process = Mock()
        process.poll.return_value = None
        process.wait.side_effect = KeyboardInterrupt
        with patch.object(cleanup.subprocess, "Popen", return_value=process), \
                patch.object(cleanup, "stop_snapshot_worker") as stop:
            with self.assertRaises(KeyboardInterrupt):
                cleanup.run_snapshot_worker(source, self.root / "copy.sqlite3")
        stop.assert_called_once_with(process)
        self.assertTrue(source.exists())

    def test_windows_worker_shutdown_includes_venv_child(self):
        process = Mock(pid=9000000)
        process.poll.return_value = None
        with patch.object(sys, "platform", "win32"), patch.object(cleanup.subprocess, "run") as run:
            cleanup.stop_snapshot_worker(process)
        self.assertEqual(run.call_args.args[0], ["taskkill.exe", "/PID", "9000000", "/T", "/F"])
        process.wait.assert_called_once_with(timeout=10)


if __name__ == "__main__":
    unittest.main()
