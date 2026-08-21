from pathlib import Path
from qdrant_client import QdrantClient, models
from config.settings import SETTINGS

BATCH_SIZE = 256

local_path = Path(SETTINGS.vector_path)
if not local_path.exists():
    raise SystemExit(
        f"No existe la base local: {local_path.resolve()}"
    )

local = QdrantClient(path=str(local_path))
server = QdrantClient(
    url=SETTINGS.qdrant_url,
    timeout=SETTINGS.qdrant_timeout_seconds,
)

server.get_collections()
name = SETTINGS.collection_name

if not local.collection_exists(name):
    raise SystemExit(f"La colección local {name} no existe.")

local_info = local.get_collection(name)
vector_config = local_info.config.params.vectors

if not server.collection_exists(name):
    server.create_collection(
        collection_name=name,
        vectors_config=vector_config,
    )

offset = None
transferred = 0
print("Migrando puntos...")

while True:
    records, offset = local.scroll(
        collection_name=name,
        limit=BATCH_SIZE,
        offset=offset,
        with_payload=True,
        with_vectors=True,
    )

    if records:
        server.upsert(
            collection_name=name,
            points=[
                models.PointStruct(
                    id=record.id,
                    vector=record.vector,
                    payload=record.payload or {},
                )
                for record in records
            ],
            wait=True,
        )
        transferred += len(records)
        print(
            f"\rPuntos migrados: {transferred}",
            end="",
            flush=True,
        )

    if offset is None:
        break

print()
server_info = server.get_collection(name)
server_count = int(server_info.points_count or 0)

print(f"Total local leído: {transferred}")
print(f"Total en servidor: {server_count}")

if server_count < transferred:
    raise SystemExit(
        "El conteo del servidor es menor que el migrado."
    )

print("MIGRACIÓN COMPLETADA.")
print("No borres runtime/qdrant todavía.")
