import ast
import hashlib
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import importlib.util
import json
from pathlib import Path
import re
import subprocess
import sys
import threading
from urllib.parse import urlparse
from urllib.request import urlopen

import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("parity", ROOT / "scripts/install_windows_mac_parity.py")
installer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(installer)
SOURCE = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT).decode().strip()
sys.path.insert(0, str(ROOT / "app/ui2"))
import windows_parity_frontend as frontend


def clone(tmp_path, ref=installer.BASE):
    root = tmp_path / "lexia"
    subprocess.run(["git", "clone", "--quiet", "--shared", str(ROOT), str(root)], check=True)
    subprocess.run(["git", "checkout", "--quiet", ref], cwd=root, check=True)
    return root


def hashes(root):
    return {str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest() for path in root.rglob("*") if path.is_file() and ".git" not in path.parts}


@pytest.mark.parametrize("ref", [installer.BASE, installer.STUDY_PREVIOUS, installer.THEMATIC_PREVIOUS, installer.STUDY, installer.SEARCH, installer.DATES, installer.MESSAGES])
def test_all_features_preflight_preserves_custom_html_and_fast_startup(tmp_path, monkeypatch, ref):
    root = clone(tmp_path, ref)
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
    for name in (installer.INDEX, "run_lexia_services.py", "app/ui2/launch_ui2.py", "app/ui2/assets/app_runtime.js"):
        path = root / name
        marker = b"\n<!-- Local Windows layout. -->\n" if name.endswith(".html") else b"\n# Local Windows startup.\n" if name.endswith(".py") else b"\n// Local Windows runtime.\n"
        path.write_bytes(path.read_bytes() + marker)
    server = root / installer.SERVER
    server.write_bytes(b"\xef\xbb\xbf" + server.read_bytes().replace(b"\n", b"\r\n"))
    before = hashes(root)
    git_index = subprocess.check_output(["git", "ls-files", "-s"], cwd=root)
    changes, guard = installer.prepare(root, SOURCE)
    assert hashes(root) == before
    assert installer.INDEX not in {str(path.relative_to(root)) for path, _, _ in changes}
    backup = installer.apply_plan(root, changes, guard)
    assert backup.is_dir()
    for name in (installer.INDEX, "run_lexia_services.py", "app/ui2/launch_ui2.py"):
        assert hashlib.sha256((root / name).read_bytes()).hexdigest() == before[name]
    assert "// Local Windows runtime." in (root / installer.RUNTIME).read_text()
    assert server.read_bytes().startswith(b"\xef\xbb\xbf")
    assert b"\n" not in server.read_bytes().replace(b"\r\n", b"")
    assert subprocess.check_output(["git", "ls-files", "-s"], cwd=root) == git_index
    assert installer.prepare(root, SOURCE)[0] == []
    settings = (root / "config/settings.py").read_text()
    assert "context_builder_study_max_chars_per_document: int = 200000" in settings
    assert "context_builder_study_max_total_chars: int = 220000" in settings
    assert "SETTINGS.context_builder_study_max_total_chars" in (root / "ai/thematic_document_study.py").read_text()
    assert '"phase": "awaiting_confirmation"' in (root / "services/ui2_delete_bridge.py").read_text()
    assert "normative_kinds = legislation_query_intent(raw)" in server.read_text(encoding="utf-8-sig")
    assert "file_modified_at" in server.read_text(encoding="utf-8-sig")


def test_conflict_in_study_ui_writes_nothing(tmp_path):
    root = clone(tmp_path)
    path = root / installer.INDEX
    path.write_text(path.read_text().replace("  const study=replace('startStudy',", "  const customStudy=replace('startStudy',"))
    before = hashes(root)
    with pytest.raises(ValueError, match="controlador"):
        installer.prepare(root, SOURCE)
    assert hashes(root) == before


def test_write_failure_rolls_back_entire_update(tmp_path, monkeypatch):
    root = clone(tmp_path)
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
    changes, guard = installer.prepare(root, SOURCE)
    before = hashes(root)
    write = installer.atomic_write
    def fail_runtime(path, data, mode=0o644):
        if str(path.relative_to(root)) == installer.RUNTIME and data != (root / installer.RUNTIME).read_bytes():
            raise OSError("simulated failure")
        write(path, data, mode)
    monkeypatch.setattr(installer, "atomic_write", fail_runtime)
    with pytest.raises(OSError):
        installer.apply_plan(root, changes, guard)
    assert hashes(root) == before


def test_html_change_after_preflight_blocks_update(tmp_path):
    root = clone(tmp_path)
    changes, guard = installer.prepare(root, SOURCE)
    (root / installer.INDEX).write_text("changed after preflight")
    before = hashes(root)
    with pytest.raises(ValueError, match="comprobación"):
        installer.apply_plan(root, changes, guard)
    assert hashes(root) == before


def test_http_delivers_updated_page_without_touching_index(tmp_path):
    original = (ROOT / installer.INDEX).read_bytes()
    tree = ast.parse((ROOT / installer.SERVER).read_text())
    handler = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "Handler")
    scope = {"SimpleHTTPRequestHandler": SimpleHTTPRequestHandler, "urlparse": urlparse, "HERE": ROOT / "app/ui2", "json": json}
    exec(compile(ast.Module(body=[handler], type_ignores=[]), "real-http-handler", "exec"), scope)
    server = ThreadingHTTPServer(("127.0.0.1", 0), scope["Handler"])
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        for path in ("/?lexia_app=1", "/index.html"):
            with urlopen(f"http://127.0.0.1:{server.server_port}" + path) as response:
                html = response.read().decode()
                assert response.status == 200
                assert "Enviar pasajes seleccionados" in html
                assert "Cancelar sin costo" in html
                assert "window.lexiaSearch320Clear=clearSearch;" in html
                assert "requestVersion!==searchVersion[searchMode]" in html
    finally:
        server.shutdown()
        server.server_close()
    assert (ROOT / installer.INDEX).read_bytes() == original


def test_rendered_javascript_is_valid():
    html = frontend.render_index((ROOT / installer.INDEX).read_text())
    scripts = re.findall(r"<script\b[^>]*>(.*?)</script>", html, flags=re.S | re.I)
    for index, script in enumerate(scripts):
        if script.strip():
            result = subprocess.run(["node", "--check", "-"], input=script.encode(), capture_output=True)
            assert result.returncode == 0, f"Script {index}: {result.stderr.decode()}"


def test_pending_search_cannot_restore_cleared_text(tmp_path):
    html = frontend.render_index((ROOT / installer.INDEX).read_text())
    script = next(script for script in re.findall(r"<script\b[^>]*>(.*?)</script>", html, flags=re.S | re.I)
                  if "/* >>> LEXIA UI2 SEARCH 3.2.0 */" in script)
    controller = tmp_path / "search-controller.js"
    controller.write_text(script)
    result = subprocess.run(["node", str(ROOT / "tests/test_windows_search_clear.js"), str(controller)], capture_output=True)
    assert result.returncode == 0, result.stderr.decode()
    assert "respuesta pendiente" in result.stdout.decode()
