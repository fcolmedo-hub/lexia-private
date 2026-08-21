from qdrant_client import QdrantClient
from config.settings import SETTINGS

client = QdrantClient(
    url=SETTINGS.qdrant_url,
    timeout=SETTINGS.qdrant_timeout_seconds,
)
collections = client.get_collections()
names = [item.name for item in collections.collections]

print("QDRANT SERVER: OK")
print(f"URL: {SETTINGS.qdrant_url}")
print("Colecciones: " + (", ".join(names) if names else "ninguna"))

if SETTINGS.collection_name in names:
    info = client.get_collection(SETTINGS.collection_name)
    print(
        f"Puntos en {SETTINGS.collection_name}: "
        f"{int(info.points_count or 0)}"
    )
