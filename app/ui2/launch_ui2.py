from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path
from urllib import request as urllib_request

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.ui2.portability import venv_python

PORT = os.environ.get("LEXIA_UI2_PORT", "8512")
BASE_URL = f"http://127.0.0.1:{PORT}"
URL = BASE_URL + "/?lexia_app=1"
py = venv_python(ROOT)

if not py.exists():
    raise SystemExit(
        f"No se encontró el Python del entorno virtual: {py}"
    )


def _ensure_ui_assets() -> str | None:
    """Registra temporalmente los assets específicos de la app y devuelve el HTML original."""
    index = HERE / "index.html"
    jurisprudence = HERE / "assets" / "jurisprudence_search.js"
    app_runtime = HERE / "assets" / "app_runtime.js"
    if not (index.exists() and jurisprudence.exists() and app_runtime.exists()):
        return None

    try:
        original = index.read_text(encoding="utf-8")
    except OSError:
        return None

    patched = original
    tags: list[str] = []

    if "assets/jurisprudence_search.js" not in patched:
        tags.append(
            '<script src="assets/jurisprudence_search.js?v=juris-mobile-5"></script>'
        )

    if "assets/app_runtime.js" not in patched:
        tags.append(
            '<script src="assets/app_runtime.js?v=app-runtime-2"></script>'
        )

    if not tags:
        return None

    block = "\n".join(tags) + "\n"
    patched = (
        patched.replace("</body>", block + "</body>", 1)
        if "</body>" in patched
        else patched + "\n" + block
    )

    try:
        index.write_text(patched, encoding="utf-8")
    except OSError:
        return None
    return original


def _restore_ui_assets(original_html: str | None) -> None:
    if original_html is None:
        return
    try:
        (HERE / "index.html").write_text(original_html, encoding="utf-8")
    except OSError:
        pass


def _wait_for_ui(url: str, process: subprocess.Popen, timeout: float = 20.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError(
                "El servidor UI2 se cerró durante el arranque."
            )
        try:
            with urllib_request.urlopen(url, timeout=0.8) as response:
                if 200 <= int(response.status) < 500:
                    return
        except Exception:
            pass
        time.sleep(0.25)
    raise RuntimeError("UI2 no respondió dentro del tiempo esperado.")


def _stop_process(process: subprocess.Popen) -> None:
    if process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=3)


def _start_windows_core_bridge():
    """En Windows, UI2 puede ser la única interfaz visible.

    El puente central antes nacía dentro de app/ui.py (Streamlit).  Al lanzar
    UI2 directamente no existe esa sesión clásica, por lo que server.py no
    encuentra ui2_delete_bridge.json.  Crear aquí la aplicación central y el
    puente mantiene borrado, mantenimiento y OCR disponibles sin abrir la UI
    clásica.  Se limita a Windows para no alterar el arranque ya estable de
    macOS.
    """
    if os.name != "nt":
        return None

    from services.application import LexIAApplication
    from services.ui2_delete_bridge import start_ui2_delete_bridge

    application = LexIAApplication()
    if not start_ui2_delete_bridge(application):
        raise RuntimeError("No se pudo iniciar el puente central de LexIA para UI2.")
    return application


def main() -> int:
    print("LexIA UI2 Desktop")
    print("Proyecto:", ROOT)
    print("UI2:", URL)

    original_index = _ensure_ui_assets()
    core_application = _start_windows_core_bridge()

    env = os.environ.copy()
    env["LEXIA_UI2_PORT"] = PORT

    popen_kwargs = {
        "cwd": str(ROOT),
        "env": env,
    }
    if os.name == "nt":
        popen_kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW

    server = subprocess.Popen(
        [str(py), str(HERE / "server.py")],
        **popen_kwargs,
    )

    try:
        _wait_for_ui(BASE_URL, server)

        try:
            import webview
        except Exception as exc:
            raise RuntimeError(
                "LexIA necesita pywebview para funcionar como aplicación de escritorio."
            ) from exc

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
        _stop_process(server)
        _restore_ui_assets(original_index)
        # Mantiene una referencia viva durante toda la sesión; al cerrar la
        # ventana, el proceso termina y con él el servidor daemon del puente.
        del core_application


if __name__ == "__main__":
    raise SystemExit(main())
