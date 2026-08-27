from __future__ import annotations

import os
import shutil
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
CREATE_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)
CREATE_NEW_PROCESS_GROUP = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)


def project_root() -> Path:
    configured = os.environ.get("LEXIA_ROOT")
    if configured:
        return Path(configured).expanduser().resolve()
    if getattr(sys, "frozen", False):
        candidate = Path(sys.executable).resolve().parent
        if (candidate / "run_lexia_services.py").exists():
            return candidate
    cwd = Path.cwd().resolve()
    if (cwd / "run_lexia_services.py").exists():
        return cwd
    default = Path("D:/LexIA_2.3_DEV")
    if default.exists():
        return default.resolve()
    raise RuntimeError("No se pudo localizar la carpeta de LexIA. Definí LEXIA_ROOT.")


def venv_python(root: Path) -> Path:
    return root / ".venv" / "Scripts" / "python.exe"


def local_appdata() -> Path:
    base = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA")
    if base:
        return Path(base)
    return Path.home() / "AppData" / "Local"


def wait_tcp(port: int, timeout: float) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.4):
                return True
        except OSError:
            time.sleep(0.25)
    return False


def docker_cli() -> Path | None:
    found = shutil.which("docker.exe") or shutil.which("docker")
    if found:
        return Path(found)
    candidates = [
        Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "Docker" / "Docker" / "resources" / "bin" / "docker.exe",
        Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "Docker" / "Docker" / "resources" / "docker.exe",
    ]
    return next((p for p in candidates if p.exists()), None)


def docker_desktop() -> Path | None:
    candidates = [
        Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "Docker" / "Docker" / "Docker Desktop.exe",
        local_appdata() / "Docker" / "Docker Desktop.exe",
    ]
    return next((p for p in candidates if p.exists()), None)


def docker_ready() -> bool:
    binary = docker_cli()
    if not binary:
        return False
    try:
        return subprocess.run(
            [str(binary), "info"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=5,
            check=False,
            creationflags=CREATE_NO_WINDOW,
        ).returncode == 0
    except Exception:
        return False


def start_existing_qdrant_container() -> bool:
    """Start the existing Qdrant container if Docker is ready but port 6333 is down."""
    binary = docker_cli()
    if not binary:
        return False

    commands = [
        [str(binary), "ps", "-a", "--filter", "ancestor=qdrant/qdrant", "--format", "{{.ID}}"],
        [str(binary), "ps", "-a", "--filter", "name=qdrant", "--format", "{{.ID}}"],
    ]
    container_id = ""
    for command in commands:
        try:
            result = subprocess.run(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                text=True,
                timeout=8,
                check=False,
                creationflags=CREATE_NO_WINDOW,
            )
        except Exception:
            continue
        ids = [line.strip() for line in (result.stdout or "").splitlines() if line.strip()]
        if ids:
            container_id = ids[0]
            break

    if not container_id:
        return False

    try:
        result = subprocess.run(
            [str(binary), "start", container_id],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=15,
            check=False,
            creationflags=CREATE_NO_WINDOW,
        )
        return result.returncode == 0
    except Exception:
        return False


def ensure_docker() -> None:
    if not docker_ready():
        desktop = docker_desktop()
        if desktop is None:
            raise RuntimeError("No se encontró Docker Desktop en Windows.")
        subprocess.Popen(
            [str(desktop)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=CREATE_NO_WINDOW,
        )

    deadline = time.monotonic() + 120
    while time.monotonic() < deadline:
        if docker_ready():
            break
        time.sleep(1)
    else:
        raise RuntimeError("Docker Desktop no quedó disponible dentro del tiempo esperado.")

    # Docker Desktop puede estar operativo sin que el contenedor persistente de
    # Qdrant haya arrancado. Intentar levantarlo explícitamente antes de fallar.
    if not wait_tcp(QDRANT_PORT, 2):
        start_existing_qdrant_container()

    if not wait_tcp(QDRANT_PORT, 60):
        raise RuntimeError(
            "Qdrant no quedó disponible en el puerto 6333. Docker inició, pero no se encontró o no pudo arrancarse el contenedor Qdrant existente."
        )


def kill_stale(root: Path) -> None:
    targets = [
        str(root / "run_lexia_services.py"),
        str(root / "app" / "ui2" / "server.py"),
        str(root / "app" / "ui2" / "launch_ui2.py"),
    ]
    script = (
        "$targets=@(" + ",".join("'" + t.replace("'", "''") + "'" for t in targets) + ");"
        "Get-CimInstance Win32_Process | Where-Object { $c=$_.CommandLine; $c -and ($targets | Where-Object { $c -like ('*'+$_+'*') }) } | "
        "ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }"
    )
    subprocess.run(
        ["powershell.exe", "-NoProfile", "-NonInteractive", "-WindowStyle", "Hidden", "-Command", script],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
        creationflags=CREATE_NO_WINDOW,
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
    tag = '<script src="assets/jurisprudence_search.js?v=juris1"></script>\n'
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


def wait_http(process: subprocess.Popen, timeout: float = 30.0) -> None:
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

    logs = local_appdata() / "LexIA" / "logs"
    logs.mkdir(parents=True, exist_ok=True)

    ensure_docker()
    kill_stale(root)

    services_log = open(logs / "services_ui2.log", "ab", buffering=0)
    flags = CREATE_NO_WINDOW | CREATE_NEW_PROCESS_GROUP
    services = subprocess.Popen(
        [str(py), str(root / "run_lexia_services.py")],
        cwd=str(root),
        stdout=services_log,
        stderr=subprocess.STDOUT,
        creationflags=flags,
    )

    server: subprocess.Popen | None = None
    original_index: str | None = None
    try:
        if not wait_tcp(BRIDGE_PORT, 40):
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
            creationflags=flags,
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
        webview.start()
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
        logs = local_appdata() / "LexIA" / "logs"
        logs.mkdir(parents=True, exist_ok=True)
        (logs / "lexia_app_error.log").write_text(str(exc) + "\n", encoding="utf-8")
        raise
