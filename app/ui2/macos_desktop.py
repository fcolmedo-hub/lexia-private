from __future__ import annotations

import os
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path
from urllib import request as urllib_request

PORT = os.environ.get("LEXIA_UI2_PORT", "8512")
URL = f"http://127.0.0.1:{PORT}"
BRIDGE_PORT = 8513
QDRANT_PORT = 6333


def project_root() -> Path:
    configured = os.environ.get("LEXIA_ROOT")
    if configured:
        return Path(configured).expanduser().resolve()
    return (Path.home() / "LexIA_2.3_DEV").resolve()


def venv_python(root: Path) -> Path:
    return root / ".venv" / "bin" / "python"


def wait_tcp(port: int, timeout: float) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.4):
                return True
        except OSError:
            time.sleep(0.25)
    return False


def docker_bin() -> Path | None:
    candidates = [
        Path("/usr/local/bin/docker"),
        Path("/opt/homebrew/bin/docker"),
        Path.home() / ".docker" / "bin" / "docker",
    ]
    return next((p for p in candidates if p.exists()), None)


def docker_ready() -> bool:
    binary = docker_bin()
    if not binary:
        return False
    try:
        return subprocess.run(
            [str(binary), "info"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=4,
            check=False,
        ).returncode == 0
    except Exception:
        return False


def ensure_docker() -> None:
    if not docker_ready():
        subprocess.run(
            ["/usr/bin/open", "-gja", "Docker"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )

    # Best effort: ocultar cualquier ventana de Docker sin condicionar el arranque.
    hide_script = (
        'tell application "System Events"\n'
        'if exists process "Docker Desktop" then set visible of process "Docker Desktop" to false\n'
        'if exists process "Docker" then set visible of process "Docker" to false\n'
        'end tell'
    )

    deadline = time.monotonic() + 90
    while time.monotonic() < deadline:
        subprocess.run(
            ["/usr/bin/osascript", "-e", hide_script],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
        if docker_ready():
            break
        time.sleep(1)
    else:
        raise RuntimeError("Docker Desktop no quedó disponible dentro del tiempo esperado.")

    if not wait_tcp(QDRANT_PORT, 90):
        raise RuntimeError("Qdrant no quedó disponible en el puerto 6333.")


def kill_stale(root: Path) -> None:
    for target in (
        root / "run_lexia_services.py",
        root / "app" / "ui2" / "server.py",
        root / "app" / "ui2" / "launch_ui2.py",
    ):
        subprocess.run(
            ["/usr/bin/pkill", "-f", str(target)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
    time.sleep(0.5)


def ensure_ui_assets(root: Path) -> str | None:
    here = root / "app" / "ui2"
    index = here / "index.html"
    script = here / "assets" / "jurisprudence_search.js"
    if not (index.exists() and script.exists()):
        return None
    marker = "assets/jurisprudence_search.js"
    original = index.read_text(encoding="utf-8")
    if marker in original:
        return None
    tag = '<script src="assets/jurisprudence_search.js?v=juris-mobile-4"></script>\n'
    patched = original.replace("</body>", tag + "</body>", 1) if "</body>" in original else original + "\n" + tag
    index.write_text(patched, encoding="utf-8")
    return original


def restore_ui_assets(root: Path, original: str | None) -> None:
    if original is None:
        return
    try:
        (root / "app" / "ui2" / "index.html").write_text(original, encoding="utf-8")
    except OSError:
        pass


def wait_http(process: subprocess.Popen, timeout: float = 25.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError("El servidor UI2 se cerró durante el arranque.")
        try:
            with urllib_request.urlopen(URL, timeout=0.8) as response:
                if 200 <= int(response.status) < 500:
                    return
        except Exception:
            pass
        time.sleep(0.25)
    raise RuntimeError("UI2 no respondió dentro del tiempo esperado.")


def stop_process(process: subprocess.Popen | None) -> None:
    if process is None or process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=3)


def main() -> int:
    root = project_root()
    py = venv_python(root)
    if not py.exists():
        raise RuntimeError(f"No se encontró el entorno virtual de LexIA: {py}")

    logs = Path.home() / "Library" / "Application Support" / "LexIA" / "logs"
    logs.mkdir(parents=True, exist_ok=True)

    ensure_docker()
    kill_stale(root)

    services_log = open(logs / "services_ui2.log", "ab", buffering=0)
    services = subprocess.Popen(
        [str(py), str(root / "run_lexia_services.py")],
        cwd=str(root),
        stdout=services_log,
        stderr=subprocess.STDOUT,
        start_new_session=True,
    )

    server: subprocess.Popen | None = None
    original_index: str | None = None
    try:
        if not wait_tcp(BRIDGE_PORT, 35):
            if services.poll() is not None:
                raise RuntimeError("Los servicios internos de LexIA finalizaron durante el arranque.")
            raise RuntimeError("LexIA no pudo iniciar su puente local de servicios (puerto 8513).")

        original_index = ensure_ui_assets(root)
        env = os.environ.copy()
        env["LEXIA_UI2_PORT"] = PORT
        server = subprocess.Popen(
            [str(py), str(root / "app" / "ui2" / "server.py")],
            cwd=str(root),
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        wait_http(server)

        import webview

        webview.create_window(
            "LexIA",
            URL,
            width=1440,
            height=900,
            min_size=(1000, 700),
            resizable=True,
        )
        webview.start(gui="cocoa")
        return 0
    finally:
        stop_process(server)
        stop_process(services)
        services_log.close()
        restore_ui_assets(root, original_index)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        # En una aplicación windowed no hay consola. Dejar un log legible.
        root = Path.home() / "Library" / "Application Support" / "LexIA" / "logs"
        root.mkdir(parents=True, exist_ok=True)
        (root / "lexia_app_error.log").write_text(str(exc) + "\n", encoding="utf-8")
        raise
