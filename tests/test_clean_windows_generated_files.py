import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest


spec = importlib.util.spec_from_file_location("cleanup", Path(__file__).parents[1] / "scripts" / "clean_windows_generated_files.py")
cleanup = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cleanup)


class CleanupTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        subprocess.run(["git", "init", "-q", str(self.root)], check=True)

    def write(self, relative, data=b"keep"):
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return path

    def cache(self):
        model = "models--qdrant--paraphrase-multilingual-MiniLM-L12-v2-onnx-Q/blobs/634d0f66c29dc934c8fa72b8a4fe91dd4d420a22f1d82a241058d4316e659a99"
        active = self.write("runtime/fastembed_cache/" + model, b"model")
        old = self.write("runtime/fastembed_cache.incompleta-20260903-200508/" + model, b"model")
        return active, old

    def test_removes_only_reviewed_generated_files(self):
        active, old = self.cache()
        experiment = self.write("runtime/experiments/lexia_document_fts_test.sqlite3", b"test")
        preview = self.write("runtime/preview_cache/office_pdf/" + "a" * 64 + ".pdf", b"preview")
        keep = [self.write(name) for name in (
            "data_test/original.pdf", "runtime/lexia_catalog.sqlite3",
            "runtime/standards/runs/costly-api-output.json",
            "backups/baseline/runtime_sqlite/lexia_catalog.sqlite3",
            ".lexia_windows_app/LexIA/LexIA.exe", ".build_lexia_windows/dist/LexIA.exe",
            "runtime/qdrant_local/points.bin", "runtime/fast_search_1_0/enabled",
            "runtime/preview_cache/office_pdf/original.pdf",
            "runtime/ui2_import_staging/pending.pdf", "runtime/secure_delete_staging/recover.pdf",
        )]
        records, directories, _ = cleanup.make_plan(self.root)
        log = self.root / "log.jsonl"
        size = cleanup.apply(self.root, records, directories, log)
        self.assertEqual(size, len(b"modeltestpreview"))
        self.assertTrue(active.exists())
        self.assertTrue(all(path.exists() for path in keep))
        self.assertTrue(all(not path.exists() for path in (old, experiment, preview)))
        self.assertEqual(sum(json.loads(line)["event"] == "deleted" for line in log.read_text().splitlines()), 3)

    def test_changed_file_is_not_deleted(self):
        path = self.write("runtime/experiments/lexia_document_fts_test.sqlite3", b"test")
        plan, folders, _ = cleanup.make_plan(self.root)
        path.write_bytes(b"changed")
        with self.assertRaises(ValueError):
            cleanup.apply(self.root, plan, folders, self.root / "log.jsonl")
        self.assertTrue(path.exists())

    def test_tracked_file_is_not_deleted(self):
        path = self.write("runtime/experiments/lexia_document_fts_test.sqlite3")
        subprocess.run(["git", "-C", str(self.root), "add", str(path)], check=True)
        with self.assertRaises(ValueError):
            cleanup.make_plan(self.root)
        self.assertTrue(path.exists())

    def test_different_active_model_preserves_quarantine(self):
        active, old = self.cache()
        active.write_bytes(b"different")
        plan, _, notes = cleanup.make_plan(self.root)
        self.assertFalse(plan)
        self.assertTrue(notes)
        self.assertTrue(old.exists())

    def test_custom_configuration_protects_candidate(self):
        path = self.write("runtime/experiments/lexia_document_fts_test.sqlite3")
        with self.assertRaises(ValueError):
            cleanup.make_plan(self.root, [path])
        self.assertTrue(path.exists())

    def test_operational_reference_protects_candidate(self):
        path = self.write("runtime/experiments/lexia_document_fts_test.sqlite3")
        self.write("app/ui2/custom.py", b"database = 'lexia_document_fts_test.sqlite3'")
        with self.assertRaises(ValueError):
            cleanup.make_plan(self.root)
        self.assertTrue(path.exists())

    def test_link_to_original_blocks_database_cleanup(self):
        target = self.write("data_test/original.pdf")
        link = self.root / "runtime/experiments/lexia_document_fts_test.sqlite3"
        link.parent.mkdir(parents=True)
        link.symlink_to(target)
        with self.assertRaises(ValueError):
            cleanup.make_plan(self.root)
        self.assertEqual(target.read_bytes(), b"keep")

    def test_quarantine_file_link_does_not_delete_target(self):
        self.cache()
        target = self.write("data_test/original.pdf")
        link = self.root / "runtime/fastembed_cache.incompleta-20260903-200508/original-link"
        link.symlink_to(target)
        plan, folders, _ = cleanup.make_plan(self.root)
        cleanup.apply(self.root, plan, folders, self.root / "log.jsonl")
        self.assertEqual(target.read_bytes(), b"keep")
        self.assertFalse(link.exists())

    def test_active_snapshot_dependency_blocks_cleanup(self):
        _, old = self.cache()
        link = self.root / "runtime/fastembed_cache/snapshot-link"
        link.symlink_to(old)
        with self.assertRaises(ValueError):
            cleanup.make_plan(self.root)
        self.assertTrue(old.exists())

    def test_directory_link_blocks_cleanup(self):
        _, old = self.cache()
        link = old.parents[2] / "linked-folder"
        link.symlink_to(self.root / "data_test", target_is_directory=True)
        (self.root / "data_test").mkdir()
        with self.assertRaises(ValueError):
            cleanup.make_plan(self.root)
        self.assertTrue(old.exists())


if __name__ == "__main__":
    unittest.main()
