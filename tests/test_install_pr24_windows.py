import subprocess
from pathlib import Path

from scripts.install_pr24_windows import changes, merge


def _git(root: Path, *args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=root, text=True).strip()


def test_merge_keeps_unrelated_local_edit_and_newlines():
    before = b"first\nsecond\nthird\n"
    after = b"first\nsecond changed\nthird\n"
    current = b"first\r\nsecond\r\nthird local\r\n"
    assert merge(current, before, after) == b"first\r\nsecond changed\r\nthird local\r\n"


def test_multiple_merge_conflicts_report_a_useful_error():
    before = b"one\ntwo\nthree\nfour\nfive\nsix\nseven\neight\n"
    local = b"one\nlocal two\nthree\nfour\nfive\nlocal six\nseven\neight\n"
    after = b"one\nnew two\nthree\nfour\nfive\nnew six\nseven\neight\n"
    try:
        merge(local, before, after)
    except ValueError as error:
        assert "cambios locales se cruzan" in str(error)
    else:
        raise AssertionError("Se esperaba una descripción del conflicto")


def test_preflight_is_atomic_when_another_file_conflicts(tmp_path):
    root = tmp_path / "project"
    root.mkdir()
    _git(root, "init", "-q")
    _git(root, "config", "user.email", "test@example.com")
    _git(root, "config", "user.name", "Test")
    (root / "one.txt").write_text("first\nsecond\nthird\n")
    (root / "two.txt").write_text("alpha\nbeta\n")
    _git(root, "add", ".")
    _git(root, "commit", "-qm", "base")
    base = _git(root, "rev-parse", "HEAD")
    (root / "one.txt").write_text("first\nsecond changed\nthird\n")
    (root / "two.txt").write_text("alpha new\nbeta\n")
    (root / "new.txt").write_text("new file\n")
    _git(root, "add", ".")
    _git(root, "commit", "-qm", "update")
    target = _git(root, "rev-parse", "HEAD")
    (root / "new.txt").unlink()
    (root / "one.txt").write_text("first\nsecond\nthird local\n")
    (root / "two.txt").write_text("alpha local\nbeta\n")
    try:
        changes(root, base, target)
    except ValueError as error:
        assert "two.txt" in str(error)
    else:
        raise AssertionError("Se esperaba un conflicto")
    assert (root / "one.txt").read_text() == "first\nsecond\nthird local\n"
    assert not (root / "new.txt").exists()

    (root / "two.txt").write_text("alpha\nbeta\n")
    planned = changes(root, base, target)
    assert planned["one.txt"] == b"first\nsecond changed\nthird local\n"
    assert planned["two.txt"] == b"alpha new\nbeta\n"
    assert planned["new.txt"] == b"new file\n"
