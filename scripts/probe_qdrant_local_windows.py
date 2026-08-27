from __future__ import annotations

import argparse
import os
import sqlite3
import sys
import time
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Esta prueba NO modifica el catalogo ni vector_indexed_hash.
# Usa un storage y una coleccion separados del Qdrant Docker/server.
os.environ["LEXIA_QDRANT_MODE"] = "local"

from qdrant_client import QdrantClient, models

from config.settings import SETTINGS
from search.embedding_service import EmbeddingService


DEFAULT_QUERY = "plazo razonable"
DEFAULT_LIMIT = 40
MAX_FRAGMENT_CHARS = 1800


def fetch_sample(limit: int) -> list[dict]:
    """Trae una muestra chica desde SQLite, sin marcar documentos como pendientes."""
    sql = """
        SELECT
            d.path,
            d.name,
            d.category,
            f.fragment_index,
            f.text_content
        FROM documents d
        JOIN fragments f
          ON f.document_path = d.path
        WHERE d.is_deleted = 0
          AND d.extraction_error IS NULL
          AND d.duplicate_of IS NULL
          AND f.text_content IS NOT NULL
          AND TRIM(f.text_content) != ''
          AND f.fragment_index = 0
        ORDER BY d.path
        LIMIT ?
    """
    with sqlite3.connect(SETTINGS.catalog_path) as connection:
        connection.row_factory = sqlite3.Row
        return [dict(row) for row in connection.execute(sql, (int(limit),)).fetchall()]


def build_probe(limit: int, query: str) -> dict:
    started = time.perf_counter()
    sample = fetch_sample(limit)
    if not sample:
        raise RuntimeError("No se encontraron fragmentos en el catalogo para probar Qdrant local.")

    storage = Path(SETTINGS.runtime_path) / "qdrant_local_probe"
    storage.mkdir(parents=True, exist_ok=True)
    collection = f"lexia_local_probe_{len(sample)}"

    print("Qdrant local probe: modo seguro", flush=True)
    print(f"Storage local: {storage.resolve()}", flush=True)
    print(f"Coleccion: {collection}", flush=True)
    print(f"Documentos/fragments de prueba: {len(sample)}", flush=True)

    embedding = EmbeddingService()
    dimension = embedding.dimension()
    client = QdrantClient(path=str(storage))

    if client.collection_exists(collection):
        client.delete_collection(collection)

    client.create_collection(
        collection_name=collection,
        vectors_config=models.VectorParams(
            size=dimension,
            distance=models.Distance.COSINE,
        ),
    )

    texts = [row["text_content"][:MAX_FRAGMENT_CHARS] for row in sample]
    vectors = embedding.embed_passages(texts)

    points = []
    for row, vector in zip(sample, vectors):
        point_id = str(uuid5(NAMESPACE_URL, f"probe::{row['path']}::{row['fragment_index']}"))
        points.append(
            models.PointStruct(
                id=point_id,
                vector=vector.tolist(),
                payload={
                    "document_name": row["name"],
                    "document_path": row["path"],
                    "category": row["category"],
                    "fragment_index": int(row["fragment_index"]),
                    "text": row["text_content"][:700],
                },
            )
        )

    client.upsert(collection_name=collection, points=points, wait=True)
    info = client.get_collection(collection)
    points_count = int(getattr(info, "points_count", 0) or 0)

    query_vector = next(iter(embedding.embed_passages([query]))).tolist()
    hits = client.search(
        collection_name=collection,
        query_vector=query_vector,
        limit=min(5, points_count),
    )

    elapsed = time.perf_counter() - started
    print("\nResultado Qdrant local probe:", flush=True)
    print(f"  puntos_insertados: {points_count}", flush=True)
    print(f"  tiempo_total: {elapsed:.2f}s", flush=True)
    print(f"  consulta: {query}", flush=True)

    for idx, hit in enumerate(hits, start=1):
        payload = hit.payload or {}
        print("", flush=True)
        print(f"  #{idx} score={float(hit.score):.4f}", flush=True)
        print(f"     categoria: {payload.get('category', '')}", flush=True)
        print(f"     documento: {payload.get('document_name', '')}", flush=True)
        print(f"     ruta: {payload.get('document_path', '')}", flush=True)

    return {
        "storage": str(storage.resolve()),
        "collection": collection,
        "points": points_count,
        "elapsed": elapsed,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Prueba segura de Qdrant local embebido para LexIA en Windows."
    )
    parser.add_argument("--limit", type=int, default=DEFAULT_LIMIT)
    parser.add_argument("--query", default=DEFAULT_QUERY)
    args = parser.parse_args()

    limit = max(1, min(int(args.limit), 500))
    build_probe(limit=limit, query=str(args.query or DEFAULT_QUERY))
    print("\nLa prueba no modifico el catalogo ni el indice Docker/server.", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
