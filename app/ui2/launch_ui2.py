from __future__ import annotations

import hashlib
import os
import re
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
STANDARDS_PORT = os.environ.get("LEXIA_STANDARDS_PORT", "8515")
BASE_URL = f"http://127.0.0.1:{PORT}"
URL = BASE_URL + "/?lexia_app=1"
STANDARDS_URL = f"http://127.0.0.1:{STANDARDS_PORT}"
py = venv_python(ROOT)

if not py.exists():
    raise SystemExit(
        f"No se encontró el Python del entorno virtual: {py}"
    )


def _versioned_script(
    asset: Path,
    prefix: str,
    *,
    source: str | None = None,
    script_id: str | None = None,
) -> str:
    digest = hashlib.sha256(asset.read_bytes()).hexdigest()[:12]
    src = source or f"assets/{asset.name}"
    id_attribute = f' id="{script_id}"' if script_id else ""
    return f'<script{id_attribute} src="{src}?v={prefix}-{digest}"></script>'


def _upsert_asset_script(
    html: str,
    asset: Path,
    prefix: str,
    pending: list[str],
    *,
    source: str | None = None,
    script_id: str | None = None,
    before_source: str | None = None,
) -> str:
    src = source or f"assets/{asset.name}"
    tag = _versioned_script(
        asset,
        prefix,
        source=src,
        script_id=script_id,
    )
    pattern = re.compile(
        rf'<script\b[^>]*\bsrc=["\']{re.escape(src)}(?:\?[^"\']*)?["\'][^>]*>\s*</script>',
        flags=re.IGNORECASE,
    )
    match = pattern.search(html)
    if match:
        updated = pattern.sub(tag, html, count=1)
        if before_source:
            anchor_pattern = re.compile(
                rf'<script\b[^>]*\bsrc=["\']{re.escape(before_source)}(?:\?[^"\']*)?["\'][^>]*>\s*</script>',
                flags=re.IGNORECASE,
            )
            anchor = anchor_pattern.search(updated)
            current = pattern.search(updated)
            if anchor and current and current.start() > anchor.start():
                updated = updated[:current.start()] + updated[current.end():]
                anchor = anchor_pattern.search(updated)
                if anchor:
                    updated = updated[:anchor.start()] + tag + "\n" + updated[anchor.start():]
        return updated
    if before_source:
        anchor = re.compile(
            rf'<script\b[^>]*\bsrc=["\']{re.escape(before_source)}(?:\?[^"\']*)?["\'][^>]*>\s*</script>',
            flags=re.IGNORECASE,
        ).search(html)
        if anchor:
            return html[:anchor.start()] + tag + "\n" + html[anchor.start():]
    pending.append(tag)
    return html


def _ensure_ui_assets() -> str | None:
    """Registra temporalmente los assets específicos de la app y devuelve el HTML original."""
    index = HERE / "index.html"
    jurisprudence = HERE / "assets" / "jurisprudence_search.js"
    search_investigation_bridge = HERE / "assets" / "search_investigation_bridge.js"
    navigator = HERE / "navigator_3_3_4a.js"
    app_runtime = HERE / "assets" / "app_runtime.js"
    standards_ui = HERE / "assets" / "standards_ui.js"
    standards_nav_fix = HERE / "assets" / "standards_nav_fix.js"
    study_layout_guard = HERE / "assets" / "study_layout_guard.js"
    startup_frame_guard = HERE / "assets" / "startup_frame_guard.css"
    if not (index.exists() and jurisprudence.exists() and app_runtime.exists()):
        return None

    try:
        original = index.read_text(encoding="utf-8")
    except OSError:
        return None

    patched = original
    head_tags: list[str] = []
    body_tags: list[str] = []

    if (
        startup_frame_guard.exists()
        and "assets/startup_frame_guard.css" not in patched
    ):
        head_tags.append(
            '<link rel="stylesheet" href="assets/startup_frame_guard.css?v=startup-frame-1">'
        )

    if navigator.exists():
        patched = _upsert_asset_script(
            patched,
            navigator,
            "navigator",
            body_tags,
            source="navigator_3_3_4a.js",
        )

    if search_investigation_bridge.exists():
        patched = _upsert_asset_script(
            patched,
            search_investigation_bridge,
            "search-investigation",
            body_tags,
            script_id="lexiaSearchInvestigationBridge",
            before_source="assets/jurisprudence_search.js",
        )

    patched = _upsert_asset_script(
        patched,
        jurisprudence,
        "jurisprudence-search",
        body_tags,
    )

    if "assets/app_runtime.js" not in patched:
        body_tags.append(
            '<script src="assets/app_runtime.js?v=app-runtime-2"></script>'
        )

    if standards_ui.exists():
        if "LEXIA_STANDARDS_PORT" not in patched:
            body_tags.append(
                f'<script>window.LEXIA_STANDARDS_PORT={STANDARDS_PORT!r};</script>'
            )
        patched = _upsert_asset_script(
            patched, standards_ui, "standards-ui", body_tags
        )

    if standards_nav_fix.exists():
        patched = _upsert_asset_script(
            patched, standards_nav_fix, "standards-nav-fix", body_tags
        )

    if (
        study_layout_guard.exists()
        and "assets/study_layout_guard.js" not in patched
    ):
        body_tags.append(
            '<script src="assets/study_layout_guard.js?v=study-layout-shared-1"></script>'
        )

    if patched == original and not head_tags and not body_tags:
        return None

    if head_tags:
        block = "\n".join(head_tags) + "\n"
        patched = (
            patched.replace("</head>", block + "</head>", 1)
            if "</head>" in patched
            else block + patched
        )

    if body_tags:
        block = "\n".join(body_tags) + "\n"
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


def _stop_process(process: subprocess.Popen | None) -> None:
    if process is None or process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=3)


def _start_windows_core_bridge():
    """En Windows, UI2 puede ser la única interfaz visible.

    El puente central antes nacía dentro de app/ui.py (Streamlit). Al lanzar
    UI2 directamente no existe esa sesión clásica, por lo que server.py no
    encuentra ui2_delete_bridge.json. Crear aquí la aplicación central y el
    puente mantiene borrado, mantenimiento y OCR disponibles sin abrir la UI
    clásica. Se limita a Windows para no alterar el arranque ya estable de
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


def _start_standards_api(env: dict[str, str], popen_kwargs: dict) -> subprocess.Popen | None:
    api_script = HERE / "standards_api.py"
    if not api_script.exists():
        return None
    api_env = dict(env)
    api_env["LEXIA_STANDARDS_PORT"] = STANDARDS_PORT
    kwargs = dict(popen_kwargs)
    kwargs["env"] = api_env
    return subprocess.Popen(
        [str(py), str(api_script)],
        **kwargs,
    )


def main() -> int:
    print("LexIA UI2 Desktop")
    print("Proyecto:", ROOT)
    print("UI2:", URL)
    print("Estándares:", STANDARDS_URL)

    original_index = _ensure_ui_assets()
    core_application = _start_windows_core_bridge()

    env = os.environ.copy()
    env["LEXIA_UI2_PORT"] = PORT
    env["LEXIA_STANDARDS_PORT"] = STANDARDS_PORT

    popen_kwargs = {
        "cwd": str(ROOT),
        "env": env,
    }
    if os.name == "nt":
        popen_kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW

    standards_api = _start_standards_api(env, popen_kwargs)
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

        # El historial de indicaciones y otros estados locales de UI deben
        # sobrevivir al cierre de LexIA. PyWebView usa modo privado por defecto.
        webview.start(private_mode=False)
        return 0
    finally:
        _stop_process(server)
        _stop_process(standards_api)
        _restore_ui_assets(original_index)
        # Mantiene una referencia viva durante toda la sesión; al cerrar la
        # ventana, el proceso termina y con él el servidor daemon del puente.
        del core_application


if __name__ == "__main__":
    raise SystemExit(main())
