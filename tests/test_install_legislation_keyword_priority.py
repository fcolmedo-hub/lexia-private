import importlib.util
from pathlib import Path
import subprocess

import pytest


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("install_norms", ROOT / "scripts/install_legislation_keyword_priority.py")
installer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(installer)


@pytest.fixture
def source(monkeypatch):
    # Use the real published-feature diff, including when this test is run at HEAD.
    patch = subprocess.check_output(["git", "diff", installer.BASE, "--", installer.SERVER], cwd=ROOT)
    helper = (ROOT / installer.HELPER).read_bytes()
    def git(_root, *args):
        if args[0] == "rev-parse":
            return b"source\n"
        if args[0] == "diff":
            return patch
        if args[0] == "show":
            return helper
        raise AssertionError(args)
    monkeypatch.setattr(installer, "git", git)


def local_copy(tmp_path, revision=installer.BASE, bom_crlf=False):
    text = subprocess.check_output(["git", "show", f"{revision}:{installer.SERVER}"], cwd=ROOT).decode()
    text += "\n# Cambio local ajeno al buscador, conservado.\n"
    path = tmp_path / installer.SERVER
    path.parent.mkdir(parents=True)
    data = (("\ufeff" + text.replace("\n", "\r\n")) if bom_crlf else text).encode()
    path.write_bytes(data)
    return path, data


@pytest.mark.parametrize("revision", [installer.BASE, "400a1013e493438d6c898a9a55bb6861e97fd691"])
def test_preflight_preserves_custom_changes_on_supported_bases(tmp_path, source, revision):
    path, original = local_copy(tmp_path, revision)
    plan = installer.prepare(tmp_path, "source")
    assert len(plan) == 2
    assert path.read_bytes() == original
    assert not (tmp_path / installer.HELPER).exists()
    updated = plan[0][2].decode()
    assert "# Cambio local ajeno al buscador, conservado." in updated
    assert "normative_kinds = legislation_query_intent(raw)" in updated


def test_backup_idempotence_and_windows_encoding(tmp_path, source, monkeypatch):
    path, original = local_copy(tmp_path, bom_crlf=True)
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
    plan = installer.prepare(tmp_path, "source")
    backup = installer.apply_plan(tmp_path, plan)
    assert (backup / installer.SERVER).read_bytes() == original
    assert path.read_bytes().startswith(b"\xef\xbb\xbf")
    assert b"\n" not in path.read_bytes().replace(b"\r\n", b"")
    assert installer.prepare(tmp_path, "source") == []


def test_conflict_blocks_both_files(tmp_path, source):
    path, _ = local_copy(tmp_path)
    original = path.read_text().replace("legal_intent = _legal_citation_intent(raw)", "legal_intent = None  # personalizado")
    path.write_text(original)
    with pytest.raises(ValueError, match="cruzan"):
        installer.prepare(tmp_path, "source")
    assert path.read_text() == original
    assert not (tmp_path / installer.HELPER).exists()


def test_existing_different_helper_blocks_all_changes(tmp_path, source):
    path, original = local_copy(tmp_path)
    (tmp_path / installer.HELPER).write_text("# versión local diferente\n")
    with pytest.raises(ValueError, match="diferente"):
        installer.prepare(tmp_path, "source")
    assert path.read_bytes() == original


def test_race_during_check_is_detected(tmp_path, source, monkeypatch):
    path, _ = local_copy(tmp_path)
    plan = installer.prepare(tmp_path, "source")
    path.write_text("# modificado después del control\n")
    with pytest.raises(ValueError, match="durante"):
        installer.apply_plan(tmp_path, plan)
    assert not (tmp_path / installer.HELPER).exists()


def test_write_failure_restores_server(tmp_path, source, monkeypatch):
    path, original = local_copy(tmp_path)
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
    plan = installer.prepare(tmp_path, "source")
    write = installer.atomic_write
    def fail_helper(target, data, mode):
        if target.name == "legislation_intent.py":
            raise OSError("simulated write failure")
        write(target, data, mode)
    monkeypatch.setattr(installer, "atomic_write", fail_helper)
    with pytest.raises(OSError):
        installer.apply_plan(tmp_path, plan)
    assert path.read_bytes() == original
    assert not (tmp_path / installer.HELPER).exists()


def test_symlink_is_rejected(tmp_path, source):
    path, _ = local_copy(tmp_path)
    target = tmp_path / "target.py"
    path.rename(target)
    path.symlink_to(target)
    with pytest.raises(ValueError, match="enlace"):
        installer.prepare(tmp_path, "source")
