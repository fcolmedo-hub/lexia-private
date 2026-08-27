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
URL = f"http://127.0.0.1:{PORT}"
py = venv_python(ROOT)

if not py.exists():
    raise SystemExit(
        f"No se encontró el Python del entorno virtual: {py}"
    )


def _ensure_ui_assets() -> None:
    """Register small optional UI2 assets without rewriting the large prototype."""
    index = HERE / "index.html"
    script = HERE / "assets" / "jurisprudence_search.js"
    if not (index.exists() and script.exists()):
        return
    marker = 'assets/jurisprudence_search.js'
    try:
        html = index.read_text(encoding="utf-8")
    except OSError:
        return
    if marker in html:
        return
    tag = '<script src="assets/jurisprudence_search.js?v=juris1"></script>\n'
    if "</body>" in html:
        html = html.replace("</body>", tag + "</body>", 1)
    else:
        html += "\n" + tag
    try:
        index.write_text(html, encoding="utf-8")
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


def main() -> int:
    print("LexIA UI2 Desktop")
    print("Proyecto:", ROOT)
    print("UI2:", URL)

    _ensure_ui_assets()

    env = os.environ.copy()
    env["LEXIA_UI2_PORT"] = PORT

    server = subprocess.Popen(
        [str(py), str(HERE / "server.py")],
        cwd=str(ROOT),
        env=env,
    )

    try:
        _wait_for_ui(URL, server)

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

        # webview.start() bloquea hasta que se cierra la última ventana.
        # Al cerrar la ventana de LexIA este proceso continúa al finally,
        # detiene server.py y permite que el launcher principal apague
        # también los servicios headless mediante su trap de salida.
        webview.start()
        return 0
    finally:
        _stop_process(server)


if __name__ == "__main__":
    raise SystemExit(main())
