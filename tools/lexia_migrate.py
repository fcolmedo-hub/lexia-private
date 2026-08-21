from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from services.release_manifest_service import (  # noqa: E402
    ReleaseManifestService,
)


def main() -> int:
    service = ReleaseManifestService(ROOT)
    manifest = service.load_manifest()
    status = service.migration_status()

    print("LexIA Migration Guard")
    print(f"Release: {manifest['platform_version']}")
    print(f"Schema release: {status['release_schema']}")
    print(f"Schema runtime: {status['runtime_schema']}")

    if status["runtime_schema"] is None:
        service.startup_guard()
        print("Baseline registrada correctamente.")
        return 0

    if status["runtime_schema"] == status["release_schema"]:
        service.startup_guard()
        print("No hay migraciones pendientes.")
        return 0

    if status["runtime_schema"] > status["release_schema"]:
        print(
            "ERROR: runtime pertenece a una versión más nueva. "
            "No se realizan cambios."
        )
        return 2

    print(
        "Hay una migración pendiente, pero esta release sólo contiene "
        "la baseline inicial. No se realizará ninguna modificación automática."
    )
    return 3


if __name__ == "__main__":
    raise SystemExit(main())
