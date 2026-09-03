import json
from pathlib import Path
from unittest.mock import Mock, patch

from services.runtime_guard import RuntimeGuard


def test_guard_writes_and_releases_state(tmp_path: Path) -> None:
    path = tmp_path / "state.json"
    guard = RuntimeGuard(path)

    guard.acquire()

    assert path.exists()
    assert guard.read_state()["pid"] is not None

    guard.release()

    assert not path.exists()


def test_guard_clears_legacy_state_when_pid_belongs_to_another_program(
    tmp_path: Path,
) -> None:
    path = tmp_path / "state.json"
    path.write_text(
        json.dumps({"pid": 2956, "hostname": "windows"}),
        encoding="utf-8",
    )
    process = Mock()
    process.is_running.return_value = True
    process.cmdline.return_value = ["C:/Windows/System32/notepad.exe"]

    with patch(
        "services.runtime_guard.psutil.Process",
        return_value=process,
    ):
        guard = RuntimeGuard(path)
        assert guard.clear_stale() is True

    assert not path.exists()
