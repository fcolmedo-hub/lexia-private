from pathlib import Path

from services.runtime_guard import RuntimeGuard


def test_guard_writes_and_releases_state(tmp_path: Path) -> None:
    path = tmp_path / "state.json"
    guard = RuntimeGuard(path)

    guard.acquire()

    assert path.exists()
    assert guard.read_state()["pid"] is not None

    guard.release()

    assert not path.exists()
