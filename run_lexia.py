import subprocess
import sys

from services.logging_service import configure_logging
from services.release_manifest_service import ReleaseManifestService
from services.runtime_guard import RuntimeGuard


def main() -> None:
    configure_logging()
    ReleaseManifestService().startup_guard()

    guard = RuntimeGuard()
    guard.clear_stale()
    guard.acquire()

    try:
        subprocess.run(
            [
                sys.executable,
                "-m",
                "streamlit",
                "run",
                "app/ui.py",
                "--server.headless=false",
            ],
            check=True,
        )
    finally:
        guard.release()


if __name__ == "__main__":
    main()
