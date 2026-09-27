"""The Windows UI repair keeps unrelated local edits and Windows line endings."""

import importlib.util
from pathlib import Path
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "install_windows_route_paint.py"
spec = importlib.util.spec_from_file_location("route_paint_installer", SCRIPT)
installer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(installer)


class RoutePaintInstallerTests(unittest.TestCase):
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
