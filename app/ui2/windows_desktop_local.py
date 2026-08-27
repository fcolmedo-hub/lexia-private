from __future__ import annotations

import os
import sys
from pathlib import Path

# Experimento Windows: usar el backend local embebido de qdrant-client en vez de
# Docker/Qdrant Server. Esto evita Docker Desktop en el arranque. El indice se
# guarda en SETTINGS.vector_path, separado del contenedor actual.
os.environ["LEXIA_QDRANT_MODE"] = "local"

import windows_desktop as base


def _local_qdrant_status() -> tuple[bool, str]:
    """Verifica que exista un indice local real antes de abrir la UI.

    Importante: esta verificacion no modifica el catalogo, no crea colecciones y
    no toca el indice Docker/server. Solo lee el storage local.
    """
    root = base.project_root()
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

    try:
        from qdrant_client import QdrantClient
        from config.settings import SETTINGS
    except Exception as exc:
        return False, f"No se pudo cargar Qdrant local: {exc}"

    storage = Path(SETTINGS.vector_path)
    collection = SETTINGS.collection_name
    if not storage.exists():
        return False, f"No existe el storage local: {storage}"

    try:
        client = QdrantClient(path=str(storage))
        if not client.collection_exists(collection):
            return False, f"No existe la coleccion local: {collection}"
        info = client.get_collection(collection)
        points = int(getattr(info, "points_count", 0) or 0)
        if points <= 0:
            return False, f"La coleccion local existe pero no tiene puntos: {collection}"
        return True, f"Indice local disponible: {collection} ({points} puntos)"
    except Exception as exc:
        return False, f"No se pudo leer el indice local: {exc}"


def _skip_docker_for_local_qdrant() -> None:
    ok, detail = _local_qdrant_status()
    base.log_startup("Qdrant local embebido activo; se omite Docker Desktop y puerto 6333")
    base.log_startup("Qdrant local: " + detail)
    if ok:
        return
    raise RuntimeError(
        "LexIA Local Qdrant es experimental y todavia no tiene un indice local valido.\n\n"
        + detail
        + "\n\nUsa el acceso normal LexIA para trabajar con el indice Docker completo. "
        + "Para habilitar este acceso local primero hay que construir el indice local."
    )


base.ensure_docker = _skip_docker_for_local_qdrant


if __name__ == "__main__":
    raise SystemExit(base.main())
