from __future__ import annotations

import subprocess
import time

import windows_desktop as base


DOCKER_READY_TIMEOUT = 1.0
DOCKER_PS_TIMEOUT = 2.0
DOCKER_START_TIMEOUT = 8.0
QDRANT_STARTUP_TIMEOUT = 240.0


def _docker_ready_fast() -> bool:
    """Probe Docker with a short timeout while Desktop is still starting."""
    binary = base.docker_cli()
    if not binary:
        return False
    try:
        return subprocess.run(
            [str(binary), "info"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=DOCKER_READY_TIMEOUT,
            check=False,
            creationflags=base.CREATE_NO_WINDOW,
        ).returncode == 0
    except Exception:
        return False


def _find_qdrant_container_fast() -> str:
    binary = base.docker_cli()
    if not binary:
        return ""

    # El contenedor de LexIA normalmente se llama qdrant. La busqueda por
    # imagen queda como fallback para instalaciones antiguas con otro nombre.
    commands = (
        [str(binary), "ps", "-a", "--filter", "name=qdrant", "--format", "{{.ID}}"],
        [str(binary), "ps", "-a", "--filter", "ancestor=qdrant/qdrant", "--format", "{{.ID}}"],
    )
    for command in commands:
        try:
            result = subprocess.run(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                text=True,
                timeout=DOCKER_PS_TIMEOUT,
                check=False,
                creationflags=base.CREATE_NO_WINDOW,
            )
        except Exception:
            continue
        ids = [line.strip() for line in (result.stdout or "").splitlines() if line.strip()]
        if ids:
            return ids[0]
    return ""


def _start_qdrant_once() -> bool:
    binary = base.docker_cli()
    container_id = _find_qdrant_container_fast()
    if not binary or not container_id:
        base.log_startup("Qdrant rapido: no se encontro contenedor existente")
        return False

    started = time.monotonic()
    try:
        result = subprocess.run(
            [str(binary), "start", container_id],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=DOCKER_START_TIMEOUT,
            check=False,
            creationflags=base.CREATE_NO_WINDOW,
        )
        base.log_startup(
            f"Qdrant rapido: docker start {container_id} -> {result.returncode} "
            f"({time.monotonic() - started:.1f}s)"
        )
        return result.returncode == 0
    except Exception as exc:
        base.log_startup(f"Qdrant rapido: error al iniciar contenedor: {exc}")
        return False


def ensure_docker_fast() -> None:
    """Cold-start Docker/Qdrant without repeated long blocking probes.

    The old launcher repeatedly executed docker info (5 s timeout), docker ps
    and docker start while Docker Desktop was booting. On a cold Windows start
    those waits accumulated. Here Docker Desktop is launched at most once,
    readiness probes are short, and the Qdrant container is started once.
    """
    started = time.monotonic()

    if base.wait_qdrant(0.35):
        base.log_startup("Qdrant rapido: ya disponible; arranque Docker omitido")
        return

    docker_was_ready = _docker_ready_fast()
    if not docker_was_ready:
        base.log_startup("Qdrant rapido: Docker no esta listo; iniciando Docker Desktop")
        base.launch_docker_desktop()
    else:
        base.log_startup("Qdrant rapido: Docker ya estaba listo")

    deadline = time.monotonic() + QDRANT_STARTUP_TIMEOUT
    docker_ready_logged = docker_was_ready
    qdrant_start_attempted = False
    last_docker_probe = 0.0

    while time.monotonic() < deadline:
        if base.wait_qdrant(0.25):
            base.log_startup(
                f"Qdrant rapido: HTTP listo en {time.monotonic() - started:.1f}s"
            )
            return

        now = time.monotonic()
        if now - last_docker_probe >= 1.25:
            last_docker_probe = now
            if _docker_ready_fast():
                if not docker_ready_logged:
                    base.log_startup(
                        f"Qdrant rapido: Docker listo en {now - started:.1f}s"
                    )
                    docker_ready_logged = True
                if not qdrant_start_attempted:
                    qdrant_start_attempted = True
                    _start_qdrant_once()

        time.sleep(0.20)

    phase = "Docker listo pero Qdrant no respondio" if docker_ready_logged else "Docker Desktop no quedo listo"
    raise RuntimeError(
        phase
        + " dentro del tiempo esperado. Ver log: "
        + str(base.logs_dir() / "lexia_windows_startup.log")
    )


base.ensure_docker = ensure_docker_fast


if __name__ == "__main__":
    raise SystemExit(base.main())
