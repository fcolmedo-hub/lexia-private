from __future__ import annotations

import signal
import threading

from services.application import LexIAApplication
from services.logging_service import configure_logging
from services.release_manifest_service import ReleaseManifestService
from services.runtime_guard import RuntimeGuard
from services.ui2_delete_bridge import start_ui2_delete_bridge


def main() -> None:
    """Run LexIA core services for UI2 without starting Streamlit."""
    configure_logging()
    ReleaseManifestService().startup_guard()

    guard = RuntimeGuard()
    guard.clear_stale()
    guard.acquire()

    stop_event = threading.Event()
    application: LexIAApplication | None = None

    def request_stop(*_args) -> None:
        stop_event.set()

    signal.signal(signal.SIGINT, request_stop)
    signal.signal(signal.SIGTERM, request_stop)

    try:
        application = LexIAApplication()

        if not start_ui2_delete_bridge(application):
            raise RuntimeError(
                "No se pudo iniciar el puente local de servicios de UI2."
            )

        application.autosync.start()
        print("LexIA Services: READY", flush=True)

        while not stop_event.wait(1.0):
            pass
    finally:
        if application is not None:
            try:
                application.autosync.stop()
            except Exception:
                pass
        guard.release()


if __name__ == "__main__":
    main()
