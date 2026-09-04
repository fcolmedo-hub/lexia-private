from __future__ import annotations

import ctypes
import json
import os
import re
import shutil
import socket
import sqlite3
import subprocess
import sys
import time
import traceback
from pathlib import Path
from urllib import request as urllib_request

import psutil

PORT = os.environ.get("LEXIA_UI2_PORT", "8512")
BASE_URL = f"http://127.0.0.1:{PORT}"
URL = BASE_URL + "/?lexia_app=1"
BRIDGE_PORT = 8513
QDRANT_PORT = 6333
QDRANT_URL = f"http://127.0.0.1:{QDRANT_PORT}/collections"
WINDOWS_APP_ID = "LexIA.Desktop"
STARTUP_MUTEX_NAME = r"Local\LexIA.Desktop.Startup"
ERROR_ALREADY_EXISTS = 183
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
        parent = candidate.parent.parent
        if (parent / "run_lexia_services.py").exists():
            return parent
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


def logs_dir() -> Path:
    path = local_appdata() / "LexIA" / "logs"
    path.mkdir(parents=True, exist_ok=True)
    return path


def log_startup(message: str) -> None:
    try:
        with (logs_dir() / "lexia_windows_startup.log").open("a", encoding="utf-8") as fh:
            fh.write(time.strftime("%Y-%m-%d %H:%M:%S") + "  " + message + "\n")
    except OSError:
        pass


def configure_taskbar_identity() -> None:
    """Give every LexIA window the same explicit Windows taskbar identity."""
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(WINDOWS_APP_ID)
        log_startup(f"Taskbar AppUserModelID: {WINDOWS_APP_ID}")
    except Exception as exc:
        log_startup(f"Taskbar AppUserModelID no disponible: {exc}")


def acquire_startup_mutex() -> tuple[bool, int | None]:
    """Allow only one Windows launcher to initialize LexIA at a time."""
    if os.name != "nt":
        return True, None

    kernel32 = ctypes.windll.kernel32
    create_mutex = kernel32.CreateMutexW
    create_mutex.argtypes = [ctypes.c_void_p, ctypes.c_bool, ctypes.c_wchar_p]
    create_mutex.restype = ctypes.c_void_p
    handle = create_mutex(None, True, STARTUP_MUTEX_NAME)
    if not handle:
        raise RuntimeError("Windows no pudo crear el bloqueo de inicio de LexIA.")
    if int(kernel32.GetLastError()) == ERROR_ALREADY_EXISTS:
        kernel32.CloseHandle(ctypes.c_void_p(handle))
        return False, None
    return True, int(handle)


def release_startup_mutex(handle: int | None) -> None:
    if os.name == "nt" and handle:
        raw_handle = ctypes.c_void_p(handle)
        try:
            ctypes.windll.kernel32.ReleaseMutex(raw_handle)
        finally:
            ctypes.windll.kernel32.CloseHandle(raw_handle)


def show_message(message: str, title: str = "LexIA") -> None:
    if os.name != "nt":
        return
    try:
        ctypes.windll.user32.MessageBoxW(None, str(message), title, 0x40)
    except Exception:
        pass


def wait_tcp(port: int, timeout: float) -> bool:
    deadline = time.monotonic() + max(timeout, 0.0)
    while True:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.35):
                return True
        except OSError:
            pass
        if time.monotonic() >= deadline:
            return False
        time.sleep(0.20)


def _http_json(url: str, timeout: float = 1.0) -> dict | None:
    req = urllib_request.Request(url, headers={"Accept": "application/json"})
    try:
        with urllib_request.urlopen(req, timeout=max(0.1, timeout)) as response:
            if not 200 <= int(response.status) < 300:
                return None
            payload = json.loads(response.read().decode("utf-8"))
            return payload if isinstance(payload, dict) else None
    except Exception:
        return None


def wait_qdrant(timeout: float) -> bool:
    """Wait for Qdrant's HTTP API, not merely for an early TCP listener."""
    deadline = time.monotonic() + max(timeout, 0.0)
    while True:
        payload = _http_json(QDRANT_URL, timeout=0.8)
        if payload and payload.get("status") == "ok" and isinstance(payload.get("result"), dict):
            return True
        if time.monotonic() >= deadline:
            return False
        time.sleep(0.25)


def docker_cli() -> Path | None:
    found = shutil.which("docker.exe") or shutil.which("docker")
    if found:
        return Path(found)
    candidates: list[Path] = []
    for key in ("ProgramFiles", "ProgramW6432", "ProgramFiles(x86)"):
        base = os.environ.get(key)
        if base:
            root = Path(base)
            candidates.extend(
                [
                    root / "Docker" / "Docker" / "resources" / "bin" / "docker.exe",
                    root / "Docker" / "Docker" / "resources" / "docker.exe",
                ]
            )
    return next((p for p in candidates if p.exists()), None)


def _docker_desktop_from_registry() -> Path | None:
    script = r"""
$keys = @(
 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\Docker Desktop.exe',
 'HKCU:\SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\Docker Desktop.exe'
)
foreach ($k in $keys) {
  try {
    $v = (Get-ItemProperty -Path $k -ErrorAction Stop).'(default)'
    if ($v -and (Test-Path $v)) { Write-Output $v; exit 0 }
  } catch {}
}
exit 1
"""
    try:
        result = subprocess.run(
            ["powershell.exe", "-NoProfile", "-NonInteractive", "-WindowStyle", "Hidden", "-Command", script],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=6,
            check=False,
            creationflags=CREATE_NO_WINDOW,
        )
    except Exception:
        return None
    for line in (result.stdout or "").splitlines():
        value = line.strip().strip('"')
        if value:
            candidate = Path(value)
            if candidate.exists():
                return candidate
    return None


def docker_desktop() -> Path | None:
    # Prefer the main desktop executable. Some installs also contain an
    # auxiliary Docker Desktop.exe below resources; launching that binary does
    # not reliably start the engine.
    registry = _docker_desktop_from_registry()
    if registry is not None and registry.parent.name.lower() != "resources":
        return registry

    candidates: list[Path] = []
    for key in ("ProgramFiles", "ProgramW6432", "ProgramFiles(x86)"):
        base = os.environ.get(key)
        if base:
            root = Path(base)
            candidates.extend([
                root / "Docker" / "Docker" / "Docker Desktop.exe",
                root / "Docker" / "Docker Desktop.exe",
                root / "DockerDesktop" / "Docker Desktop.exe",
            ])

    lad = local_appdata()
    candidates.extend([
        lad / "Docker" / "Docker Desktop.exe",
        lad / "Programs" / "Docker" / "Docker" / "Docker Desktop.exe",
        lad / "Programs" / "Docker" / "Docker Desktop.exe",
        lad / "Programs" / "DockerDesktop" / "Docker Desktop.exe",
    ])

    cli = docker_cli()
    if cli is not None:
        current = cli.parent
        while current.parent != current:
            if current.name.lower() == "resources":
                candidates.insert(0, current.parent / "Docker Desktop.exe")
                break
            current = current.parent

    seen: set[str] = set()
    for candidate in candidates:
        key = str(candidate).lower()
        if key in seen:
            continue
        seen.add(key)
        if candidate.exists() and candidate.parent.name.lower() != "resources":
            return candidate

    return None


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
        log_startup("Qdrant: no se encontró contenedor existente")
        return False

    try:
        result = subprocess.run(
            [str(binary), "start", container_id],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=20,
            check=False,
            creationflags=CREATE_NO_WINDOW,
        )
        log_startup(f"Qdrant: docker start {container_id} -> {result.returncode}")
        return result.returncode == 0
    except Exception as exc:
        log_startup(f"Qdrant: error al iniciar contenedor: {exc}")
        return False


def launch_docker_desktop() -> None:
    desktop = docker_desktop()
    if desktop is None:
        binary = docker_cli()
        hint = f" docker.exe={binary}" if binary else " docker.exe=no encontrado"
        raise RuntimeError("No se encontró el ejecutable principal de Docker Desktop en Windows." + hint)

    log_startup(f"Docker Desktop: ejecutable principal {desktop}")
    try:
        process = subprocess.Popen(
            [str(desktop)],
            cwd=str(desktop.parent),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=CREATE_NO_WINDOW,
        )
        log_startup(f"Docker Desktop: proceso lanzado pid={process.pid}")
        return
    except Exception as exc:
        log_startup(f"Docker Desktop: Popen falló: {exc}")

    try:
        os.startfile(str(desktop))
        log_startup("Docker Desktop: lanzado mediante os.startfile")
    except Exception as exc:
        log_startup(f"Docker Desktop: os.startfile falló: {exc}")
        raise RuntimeError(f"No se pudo iniciar Docker Desktop: {desktop}") from exc


def ensure_docker() -> None:
    start = time.monotonic()

    # A TCP listener can appear before Qdrant has finished loading. Wait for its
    # real HTTP API so LexIA cannot fall back to an empty state during startup.
    if wait_qdrant(0.8):
        log_startup("Qdrant ya estaba disponible; se omite Docker Desktop")
        return

    if not docker_ready():
        launch_docker_desktop()

    deadline = time.monotonic() + 420
    last_qdrant_start = 0.0
    while time.monotonic() < deadline:
        if wait_qdrant(0.8):
            log_startup(f"Qdrant disponible tras {time.monotonic() - start:.1f}s")
            return

        if docker_ready():
            if time.monotonic() - last_qdrant_start > 8:
                start_existing_qdrant_container()
                last_qdrant_start = time.monotonic()
            if wait_qdrant(1.5):
                log_startup(f"Qdrant disponible tras iniciar contenedor: {time.monotonic() - start:.1f}s")
                return

        time.sleep(1)

    raise RuntimeError(
        "Docker Desktop no quedó disponible dentro del tiempo esperado. "
        "Abrí Docker Desktop manualmente una vez y verificá que termine de iniciar; "
        "luego cerrá LexIA y probá nuevamente. Ver log: " + str(logs_dir() / "lexia_windows_startup.log")
    )


def kill_stale(root: Path) -> None:
    """Stop orphaned LexIA source processes and verify that they exited.

    Matching through psutil avoids quoting and path-separator differences in
    PowerShell/CIM that previously allowed run_lexia_services.py to survive.
    """
    root_marker = str(root.resolve()).replace("\\", "/").casefold()
    script_markers = (
        "/run_lexia.py",
        "/run_lexia_services.py",
        "/app/ui2/server.py",
        "/app/ui2/launch_ui2.py",
    )
    matched: list[psutil.Process] = []

    for process in psutil.process_iter(["pid", "cmdline"]):
        if process.pid == os.getpid():
            continue
        try:
            command = " ".join(
                process.info.get("cmdline") or []
            ).replace("\\", "/").casefold()
        except (psutil.NoSuchProcess, psutil.ZombieProcess, psutil.AccessDenied):
            continue
        if (
            root_marker not in command
            or not any(marker in command for marker in script_markers)
        ):
            continue
        try:
            process.terminate()
            matched.append(process)
        except (psutil.NoSuchProcess, psutil.ZombieProcess):
            continue
        except psutil.AccessDenied as exc:
            raise RuntimeError(
                f"No se pudo cerrar el proceso anterior de LexIA PID {process.pid}."
            ) from exc

    _gone, alive = psutil.wait_procs(matched, timeout=4.0)
    for process in alive:
        try:
            process.kill()
        except (psutil.NoSuchProcess, psutil.ZombieProcess):
            pass
        except psutil.AccessDenied as exc:
            raise RuntimeError(
                f"No se pudo finalizar el proceso anterior de LexIA PID {process.pid}."
            ) from exc

    _gone, still_alive = psutil.wait_procs(alive, timeout=4.0)
    if still_alive:
        pids = ", ".join(str(process.pid) for process in still_alive)
        raise RuntimeError(
            "No se pudieron cerrar procesos anteriores de LexIA: PID " + pids
        )

    if matched:
        log_startup(
            "Procesos anteriores cerrados antes del inicio: "
            + ", ".join(str(process.pid) for process in matched)
        )


def ensure_ui_assets(root: Path) -> str | None:
    here = root / "app" / "ui2"
    index = here / "index.html"
    script = here / "assets" / "jurisprudence_search.js"
    live_badge_cleanup = (
        here / "assets" / "windows_live_badge_cleanup.js"
    )
    startup_frame_guard = here / "assets" / "startup_frame_guard.css"
    app_runtime = here / "assets" / "app_runtime.js"
    if not (
        index.exists()
        and script.exists()
        and live_badge_cleanup.exists()
        and app_runtime.exists()
    ):
        return None

    original = index.read_text(encoding="utf-8")
    patched = original
    changed = False

    if startup_frame_guard.exists() and "assets/startup_frame_guard.css" not in patched:
        tag = '<link rel="stylesheet" href="assets/startup_frame_guard.css?v=startup-frame-1">\n'
        patched = patched.replace("</head>", tag + "</head>", 1) if "</head>" in patched else tag + patched
        changed = True

    if "assets/jurisprudence_search.js" not in patched:
        tag = '<script src="assets/jurisprudence_search.js?v=juris-mobile-7"></script>\n'
        patched = patched.replace("</body>", tag + "</body>", 1) if "</body>" in patched else patched + "\n" + tag
        changed = True

    # Casos y los ajustes comunes de UI2 se cargan también en Windows.
    # Reemplazamos la versión temporal para impedir que PyWebView reutilice
    # un runtime anterior entre aperturas.
    runtime_tag = '<script src="assets/app_runtime.js?v=app-runtime-3"></script>'
    if "assets/app_runtime.js" in patched:
        refreshed = re.sub(
            r'<script[^>]+src=["\'][^"\']*assets/app_runtime\.js[^"\']*["\'][^>]*>\s*</script>',
            runtime_tag,
            patched,
            flags=re.IGNORECASE,
        )
        if refreshed != patched:
            patched = refreshed
            changed = True
    else:
        tag = runtime_tag + "\n"
        patched = patched.replace("</body>", tag + "</body>", 1) if "</body>" in patched else patched + "\n" + tag
        changed = True

    if "assets/windows_live_badge_cleanup.js" not in patched:
        tag = (
            '<script src="assets/windows_live_badge_cleanup.js'
            '?v=windows-live-cleanup-1"></script>\n'
        )
        patched = patched.replace("</body>", tag + "</body>", 1) if "</body>" in patched else patched + "\n" + tag
        changed = True

    if not changed:
        return None

    index.write_text(patched, encoding="utf-8")
    return original


def restore_ui_assets(root: Path, original: str | None) -> None:
    if original is None:
        return
    try:
        (root / "app" / "ui2" / "index.html").write_text(original, encoding="utf-8")
    except OSError:
        pass


def catalog_document_count(root: Path, timeout: float = 15.0) -> int:
    """Read the existing catalog before launching the UI.

    A locked or unreadable production catalog is a startup error. Treating it
    as an empty library is misleading and was the cause of intermittent zero
    counters in the desktop window.
    """
    configured = os.environ.get("LEXIA_RUNTIME_PATH")
    runtime = Path(configured).expanduser() if configured else root / "runtime"
    catalog = runtime / "lexia_catalog.sqlite3"
    if not catalog.exists():
        return 0

    deadline = time.monotonic() + max(timeout, 0.0)
    last_error: Exception | None = None
    while True:
        try:
            uri = catalog.resolve().as_uri() + "?mode=ro"
            connection = sqlite3.connect(uri, uri=True, timeout=1.0)
            try:
                return int(connection.execute(
                    "SELECT COUNT(*) FROM documents WHERE COALESCE(is_deleted, 0)=0"
                ).fetchone()[0])
            finally:
                # El context manager de sqlite3 confirma/revierte, pero no
                # cierra la conexión. En Windows eso mantiene el archivo
                # bloqueado hasta que el recolector libera el objeto.
                connection.close()
        except Exception as exc:
            last_error = exc
        if time.monotonic() >= deadline:
            raise RuntimeError(
                f"No se pudo leer el catálogo de LexIA antes de iniciar: {catalog}. "
                f"Detalle: {last_error}"
            ) from last_error
        time.sleep(0.35)


def wait_ui_ready(
    process: subprocess.Popen,
    expected_documents: int,
    timeout: float = 60.0,
) -> None:
    """Wait only for the essential services required to open the desktop UI.

    The full /api/live snapshot includes catalog statistics that can take longer
    than the HTTP probe on large libraries. A timeout there must not be treated
    as an empty catalog: catalog_document_count() already validated the real
    catalog before the services were launched.
    """
    deadline = time.monotonic() + timeout
    last_detail = "servicios todavía no disponibles"
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError("El servidor UI2 se cerró durante el arranque.")

        health = _http_json(BASE_URL + "/api/health", timeout=0.8)
        core = _http_json(BASE_URL + "/api/maintenance-live", timeout=1.2)

        ui_ready = isinstance(health, dict) and health.get("ok") is True
        core_ready = isinstance(core, dict) and core.get("ok") is True
        if ui_ready and core_ready:
            log_startup(
                "UI2 lista: servicios esenciales disponibles; "
                f"catálogo validado antes del inicio={expected_documents}"
            )
            return

        if not ui_ready:
            last_detail = "el servidor UI2 todavía no respondió"
        else:
            last_detail = "el puente de servicios centrales todavía no respondió"
        time.sleep(0.30)

    raise RuntimeError(
        "LexIA no alcanzó un estado consistente dentro del tiempo esperado; "
        + last_detail
    )

def stop_process(process: subprocess.Popen | None) -> None:
    if process is None or process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=3)


def _tail_text(path: Path, lines: int = 30) -> str:
    try:
        content = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return ""
    return "\n".join(content[-lines:])


def _run() -> int:
    root = project_root()
    py = venv_python(root)
    if not py.exists():
        raise RuntimeError(f"No se encontró el entorno virtual de LexIA: {py}")

    logs = logs_dir()
    log_startup("===== inicio LexIA Windows =====")
    configure_taskbar_identity()

    ensure_docker()
    kill_stale(root)
    expected_documents = catalog_document_count(root)
    log_startup(f"Catálogo previo al inicio: {expected_documents} documento(s)")

    services_log_path = logs / "services_ui2.log"
    services_log = open(services_log_path, "ab", buffering=0)
    flags = CREATE_NO_WINDOW | CREATE_NEW_PROCESS_GROUP
    services = subprocess.Popen(
        [str(py), str(root / "run_lexia_services.py")],
        cwd=str(root),
        stdout=services_log,
        stderr=subprocess.STDOUT,
        creationflags=flags,
    )

    server: subprocess.Popen | None = None
    server_log = None
    original_index: str | None = None
    try:
        if not wait_tcp(BRIDGE_PORT, 150):
            tail = _tail_text(services_log_path)
            if services.poll() is not None:
                detail = "Los servicios internos de LexIA finalizaron durante el arranque."
            else:
                detail = "LexIA no pudo iniciar su puente local de servicios (puerto 8513)."
            if tail:
                detail += "\n\nÚltimas líneas de services_ui2.log:\n" + tail
            raise RuntimeError(detail)

        original_index = ensure_ui_assets(root)
        env = os.environ.copy()
        env["LEXIA_UI2_PORT"] = PORT
        server_log_path = logs / "ui2_server.log"
        server_log = open(server_log_path, "ab", buffering=0)
        server = subprocess.Popen(
            [str(py), str(root / "app" / "ui2" / "server.py")],
            cwd=str(root),
            env=env,
            stdout=server_log,
            stderr=subprocess.STDOUT,
            creationflags=flags,
        )
        wait_ui_ready(server, expected_documents)

        import webview

        webview.create_window("LexIA", URL, width=1440, height=900, min_size=(1000, 700), resizable=True)
        # PyWebView usa modo privado por defecto; desactivarlo conserva
        # localStorage entre reinicios (por ejemplo Indicaciones recientes).
        webview.start(private_mode=False)
        return 0
    finally:
        stop_process(server)
        stop_process(services)
        if server_log is not None:
            server_log.close()
        services_log.close()
        restore_ui_assets(root, original_index)


def main() -> int:
    acquired, mutex = acquire_startup_mutex()
    if not acquired:
        log_startup("Inicio duplicado ignorado: LexIA ya se está iniciando o está abierta")
        show_message(
            "LexIA ya se está iniciando o está abierta. Esperá a que aparezca "
            "la ventana; no es necesario volver a abrir el acceso directo."
        )
        return 0
    try:
        return _run()
    finally:
        release_startup_mutex(mutex)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        logs = logs_dir()
        error_path = logs / "lexia_app_error.log"
        error_path.write_text(traceback.format_exc(), encoding="utf-8")
        log_startup(f"ERROR: {exc}")
        if getattr(sys, "frozen", False):
            show_message(
                f"LexIA no pudo completar el arranque.\n\n{exc}\n\n"
                f"Diagnóstico: {error_path}",
                "LexIA — error de inicio",
            )
            raise SystemExit(1)
        raise
