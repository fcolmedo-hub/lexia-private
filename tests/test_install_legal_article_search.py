"""Exercise the compatibility installer against the actual published Git patch."""
import importlib.util
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch


SOURCE = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("article_installer", SOURCE / "tools/install_legal_article_search.py")
installer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(installer)


class InstallationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        for commit in (installer.BASE, installer.FIX):
            if installer.git(SOURCE, "cat-file", "-e", commit + "^{commit}", check=False).returncode:
                raise unittest.SkipTest("Integration test requires the published fix and its base in Git history")

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "repo"
        subprocess.run(["git", "clone", "--quiet", "--shared", "--no-checkout", str(SOURCE), str(self.root)], check=True)
        existing = [installer.RUNTIME, "app/ui2/server.py", "tests/test_content_search_legislation_priority.py", "app/ui2/index.html"]
        installer.git(self.root, "checkout", installer.BASE, "--", *existing)
        # Simulate the Mac's locally customized runtime and HTML entrypoint.
        self.runtime = self.root / installer.RUNTIME
        original = self.runtime.read_bytes()
        self.runtime.write_bytes(original.replace(b"\n", b"\r\n") + b"\r\n// Local Mac customization\r\n")
        self.html = self.root / "app/ui2/index.html"
        self.html.write_bytes(self.html.read_bytes() + b"\n<!-- Local HTML customization -->\n")
        self.before = self.contents()
        self.index_before = (self.root / ".git/index").read_bytes()

    def contents(self):
        return {name: (self.root / name).read_bytes() if (self.root / name).exists() else None for name in (*installer.FILES, installer.RUNTIME, "app/ui2/index.html")}

    def install(self):
        return installer.install(self.root, Path(self.temp.name))

    def test_custom_runtime_preserved_backup_and_repeated_install(self):
        backup = self.install()
        self.assertTrue(self.runtime.read_bytes().startswith(self.before[installer.RUNTIME]))
        self.assertEqual(self.runtime.read_bytes().count(b"locator.src='assets/legal_article_preview.js?v=1'"), 1)
        self.assertEqual((backup / installer.RUNTIME).read_bytes(), self.before[installer.RUNTIME])
        self.assertEqual(self.html.read_bytes(), self.before["app/ui2/index.html"])
        for name in installer.FILES:
            expected = installer.git(self.root, "show", installer.FIX + ":" + name).stdout
            self.assertEqual((self.root / name).read_bytes(), expected, name)
        after = self.contents()
        self.assertIsNone(self.install())
        self.assertEqual(self.contents(), after)
        self.assertEqual((self.root / ".git/index").read_bytes(), self.index_before)

    def test_conflicting_server_stops_without_modifying_any_file(self):
        server = self.root / "app/ui2/server.py"
        server.write_text("# Incompatible local server\n")
        before = self.contents()
        with self.assertRaisesRegex(RuntimeError, "Necesita revisión"):
            self.install()
        self.assertEqual(self.contents(), before)
        self.assertEqual((self.root / ".git/index").read_bytes(), self.index_before)

    def test_runtime_write_failure_restores_all_changes(self):
        original_write = installer.atomic_write
        failed = False

        def write(path, content, mode):
            nonlocal failed
            if path == self.runtime and not failed:
                failed = True
                raise OSError("Simulated write failure")
            return original_write(path, content, mode)

        with patch.object(installer, "atomic_write", side_effect=write):
            with self.assertRaisesRegex(RuntimeError, "se restauraron"):
                self.install()
        self.assertEqual(self.contents(), self.before)
        self.assertEqual((self.root / ".git/index").read_bytes(), self.index_before)


if __name__ == "__main__":
    unittest.main()
