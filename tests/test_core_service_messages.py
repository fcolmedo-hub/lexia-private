import ast
import importlib.util
import io
import json
from pathlib import Path
import subprocess
from urllib import error as urllib_error, request as urllib_request

import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("install_messages", ROOT / "scripts/install_core_service_messages.py")
installer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(installer)


def proxy(state):
    tree = ast.parse((ROOT / installer.SERVER).read_text())
    nodes = [node for node in tree.body if isinstance(node, (ast.ClassDef, ast.FunctionDef)) and node.name in {"_DeleteBridgeError", "_delete_bridge_request"}]
    namespace = {"json": json, "DELETE_BRIDGE_STATE": state, "urllib_request": urllib_request, "urllib_error": urllib_error}
    exec(compile(ast.Module(body=nodes, type_ignores=[]), "core-proxy", "exec"), namespace)
    return namespace["_delete_bridge_request"], namespace["_DeleteBridgeError"]


@pytest.mark.parametrize("endpoint", ["/api/delete-file", "/api/research-start", "/api/maintenance-action"])
@pytest.mark.parametrize("failure", ["missing", "invalid", "disconnected"])
def test_all_operations_report_core_service_instead_of_classic_ui(tmp_path, monkeypatch, endpoint, failure):
    state = tmp_path / "bridge.json"
    if failure == "invalid":
        state.write_text('{"port":0}')
    if failure == "disconnected":
        state.write_text(json.dumps({"port": 8513, "token": "x" * 32}))
    def fail(*_args, **_kwargs):
        raise urllib_error.URLError(ConnectionRefusedError("not listening"))
    monkeypatch.setattr(urllib_request, "urlopen", fail)
    call, error = proxy(state)
    with pytest.raises(error) as caught:
        call("POST", endpoint, {"path": "document.pdf"})
    assert caught.value.status == 503
    assert "servicio interno de LexIA" in str(caught.value)
    assert "interfaz clásica" not in str(caught.value)
    assert "borrado" not in str(caught.value)


def test_http_rejection_preserves_specific_message_and_status(tmp_path, monkeypatch):
    state = tmp_path / "bridge.json"
    state.write_text(json.dumps({"port": 8513, "token": "x" * 32}))
    def fail(*_args, **_kwargs):
        raise urllib_error.HTTPError("http://127.0.0.1:8513/", 409, "Conflict", {}, io.BytesIO(b'{"error":"OCR trabajando"}'))
    monkeypatch.setattr(urllib_request, "urlopen", fail)
    call, error = proxy(state)
    with pytest.raises(error) as caught:
        call("POST", "/api/delete-file", {})
    assert caught.value.status == 409
    assert str(caught.value) == "OCR trabajando"


@pytest.mark.parametrize("response", [[], {"ok": True, "started": True}])
def test_available_service_and_malformed_response(tmp_path, monkeypatch, response):
    state = tmp_path / "bridge.json"
    state.write_text(json.dumps({"port": 8513, "token": "x" * 32}))
    class Response(io.BytesIO):
        status = 202
    requests = []
    def respond(request, **kwargs):
        requests.append(request)
        return Response(json.dumps(response).encode())
    monkeypatch.setattr(urllib_request, "urlopen", respond)
    call, error = proxy(state)
    if isinstance(response, dict):
        assert call("POST", "/api/research-start", {"query": "test"}) == (response, 202)
        assert requests[0].get_header("X-lexia-delete-token") == "x" * 32
    else:
        with pytest.raises(error, match="servicio interno"):
            call("POST", "/api/research-start", {})


@pytest.mark.parametrize("ref", ["400a1013e493438d6c898a9a55bb6861e97fd691", "bb3d877aa2e258ae617101b0f027ef7b0d58c063"])
@pytest.mark.parametrize("encoding", ["lf", "bom-crlf"])
def test_installer_preserves_other_modifications_and_is_idempotent(ref, encoding):
    original = subprocess.check_output(["git", "show", f"{ref}:{installer.SERVER}"], cwd=ROOT)
    original += b"\n# Local change: retain this comment.\n"
    if encoding == "bom-crlf":
        original = b"\xef\xbb\xbf" + original.replace(b"\n", b"\r\n")
    updated = installer.prepare(original)
    assert b"# Local change: retain this comment." in updated
    assert installer.prepare(updated) == updated
    restored = updated
    newline = "\r\n" if encoding == "bom-crlf" else "\n"
    for before, after, _count in installer.REPLACEMENTS:
        restored = restored.replace(after.replace("\n", newline).encode(), before.replace("\n", newline).encode())
    assert restored == original


def test_backup_and_atomic_failure_leave_original_intact(tmp_path, monkeypatch):
    path = tmp_path / "server.py"
    original = b"# original\n"
    path.write_bytes(original)
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
    def fail(*args):
        raise OSError("simulated failure")
    monkeypatch.setattr(installer.os, "replace", fail)
    with pytest.raises(OSError):
        installer.install(path, original, b"# updated\n")
    assert path.read_bytes() == original
    assert next(tmp_path.glob("lexia-avisos-*/server.py")).read_bytes() == original


def test_local_message_conflict_blocks_install():
    original = subprocess.check_output(["git", "show", f"400a1013e493438d6c898a9a55bb6861e97fd691:{installer.SERVER}"], cwd=ROOT)
    original = original.replace("No se encontró su puente local de borrado seguro.".encode(), b"Mensaje personalizado.", 1)
    with pytest.raises(ValueError, match="cambios locales"):
        installer.prepare(original)
