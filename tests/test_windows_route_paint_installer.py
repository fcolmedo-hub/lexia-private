"""The Windows UI repair keeps unrelated local edits and Windows line endings."""

import importlib.util
from pathlib import Path
import os
import subprocess
import tempfile
import unittest
from unittest.mock import patch


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "install_windows_route_paint.py"
spec = importlib.util.spec_from_file_location("route_paint_installer", SCRIPT)
installer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(installer)


class RoutePaintInstallerTests(unittest.TestCase):
    def test_check_and_install_on_old_checkout_with_local_ui_changes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "checkout"
            root.mkdir()
            def git(*args):
                return subprocess.check_output(["git", *args], cwd=root).decode().strip()
            git("init", "-q")
            git("config", "user.name", "Test")
            git("config", "user.email", "test@example.com")
            paths = [root / path for path in installer.FILES]
            for path in paths:
                path.parent.mkdir(parents=True, exist_ok=True)
            old_block = "    if(!state){\n      page.innerHTML='loading';\n      return;\n    }"
            new_block = "    if(!state){\n      page.innerHTML='heading';\n      return;\n    }"
            paths[0].write_text("header\n" + old_block + "\nfooter\n")
            paths[1].write_text("base runtime\n")
            paths[2].write_text("base badge\n")
            git("add", ".")
            git("commit", "-qm", "before")
            before = git("rev-parse", "HEAD")
            paths[0].write_text("header\n" + new_block + "\nfooter\n")
            git("add", ".")
            git("commit", "-qm", "maintenance")
            base = git("rev-parse", "HEAD")
            paths[1].write_text("fixed runtime\n")
            paths[2].write_text("fixed badge\n")
            git("add", ".")
            git("commit", "-qm", "badge")
            git("fetch", "-q", ".", "HEAD")
            git("checkout", "-q", before)
            paths[0].write_bytes(("header\n" + old_block + "\nlocal customization\nfooter\n").replace("\n", "\r\n").encode())
            home = Path(directory) / "user"
            (home / "Desktop").mkdir(parents=True)
            previous = Path.cwd()
            try:
                os.chdir(root)
                with patch.object(installer, "BASE", base), patch.object(installer, "MAINTENANCE_BEFORE", before), patch.object(installer.Path, "home", return_value=home):
                    installer.main(["--check"])
                    self.assertEqual(paths[1].read_text(), "base runtime\n")
                    installer.main([])
                    installer.main([])
            finally:
                os.chdir(previous)
            self.assertIn(b"heading';\r\n", paths[0].read_bytes())
            self.assertIn(b"local customization\r\n", paths[0].read_bytes())
            self.assertEqual(paths[1].read_text(), "fixed runtime\n")
            self.assertEqual(paths[2].read_text(), "fixed badge\n")
            backups = list((home / "Desktop").glob("lexia-pantallas-windows-*"))
            self.assertEqual(len(backups), 1)
            self.assertIn(b"loading';\r\n", (backups[0] / installer.FILES[0]).read_bytes())

    def test_maintenance_surgical_edit_keeps_local_work_and_crlf(self):
        before = b"header\n    if(!state){\n      page.innerHTML='loading';\n      return;\n    }\nfooter\n"
        after = b"header\n    if(!state){\n      page.innerHTML='heading and tabs';\n      bind();\n      return;\n    }\nfooter\n"
        current = before.replace(b"footer", b"local change\nfooter").replace(b"\n", b"\r\n")
        result = installer.prepare("app/ui2/assets/maintenance.js", current, before, after)
        self.assertIn(b"heading and tabs';\r\n", result)
        self.assertIn(b"local change\r\n", result)
        self.assertNotIn(b"\n", result.replace(b"\r\n", b""))
        self.assertEqual(installer.prepare("app/ui2/assets/maintenance.js", result, before, after), result)

    def test_modified_maintenance_block_refuses_to_overwrite(self):
        before = b"    if(!state){\n      page.innerHTML='loading';\n      return;\n    }"
        after = b"    if(!state){\n      page.innerHTML='heading';\n      return;\n    }"
        with self.assertRaisesRegex(ValueError, "cambios propios"):
            installer.prepare("app/ui2/assets/maintenance.js", before.replace(b"loading", b"custom"), before, after)

    def test_shared_asset_requires_known_local_version(self):
        path = "app/ui2/assets/app_runtime.js"
        self.assertEqual(installer.prepare(path, b"base\r\n", b"base\n", b"fixed\n"), b"fixed\r\n")
        self.assertEqual(installer.prepare(path, b"fixed\r\n", b"base\n", b"fixed\n"), b"fixed\r\n")
        with self.assertRaisesRegex(ValueError, "cambios locales"):
            installer.prepare(path, b"custom\n", b"base\n", b"fixed\n")


if __name__ == "__main__":
    unittest.main()
