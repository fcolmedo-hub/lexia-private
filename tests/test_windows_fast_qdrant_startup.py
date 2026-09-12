from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_default_windows_build_uses_fast_launcher() -> None:
    source = (ROOT / "scripts/rebuild_lexia_app_windows.ps1").read_text(
        encoding="utf-8"
    )
    assert "windows_desktop_fast.py" in source
    assert "windows_desktop_local.py" in source


def test_fast_launcher_uses_short_docker_probe_and_single_qdrant_start() -> None:
    source = (ROOT / "app/ui2/windows_desktop_fast.py").read_text(
        encoding="utf-8"
    )

    assert "DOCKER_READY_TIMEOUT = 1.0" in source
    assert "DOCKER_PS_TIMEOUT = 2.0" in source
    assert "DOCKER_START_TIMEOUT = 8.0" in source
    assert "qdrant_start_attempted = False" in source
    assert "if not qdrant_start_attempted:" in source
    assert "qdrant_start_attempted = True" in source
    assert "base.ensure_docker = ensure_docker_fast" in source


def test_fast_launcher_logs_startup_phases() -> None:
    source = (ROOT / "app/ui2/windows_desktop_fast.py").read_text(
        encoding="utf-8"
    )

    assert "Docker listo en" in source
    assert "docker start" in source
    assert "HTTP listo en" in source
