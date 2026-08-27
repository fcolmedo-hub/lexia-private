from __future__ import annotations

import os
import sys

# Experimento Windows: usar el backend local embebido de qdrant-client en vez de
# Docker/Qdrant Server. Esto evita Docker Desktop en el arranque. El índice se
# guarda en SETTINGS.vector_path, separado del contenedor actual.
os.environ["LEXIA_QDRANT_MODE"] = "local"

import windows_desktop as base


def _skip_docker_for_local_qdrant() -> None:
    base.log_startup("Qdrant local embebido activo; se omite Docker Desktop y puerto 6333")


base.ensure_docker = _skip_docker_for_local_qdrant


if __name__ == "__main__":
    raise SystemExit(base.main())
