import sqlite3
from pathlib import Path
import time
import urllib.request
import urllib.error
from uuid import NAMESPACE_URL, uuid5

from qdrant_client import QdrantClient, models

from config.settings import SETTINGS
from models.document import Document
from models.search_result import SearchResult
from search.embedding_service import EmbeddingService


class VectorStore:
    def __init__(
        self,
        embedding_service: EmbeddingService,
        path: str | Path = SETTINGS.vector_path,
        collection_name: str = SETTINGS.collection_name,
    ):
        self.embedding_service = embedding_service
        self.collection_name = collection_name
        self.connection_mode = self._resolve_mode()
        self.client = self._create_client(path)
        self._ensure_collection()

    def _resolve_mode(self) -> str:
        configured = str(
            getattr(SETTINGS, "qdrant_mode", "auto")
        ).strip().casefold()

        if configured not in {"auto", "server", "local"}:
            raise ValueError(
                "qdrant_mode debe ser auto, server o local."
            )

        if configured == "local":
            return "local"

        if self._server_available():
            return "server"

        if configured == "server":
            raise RuntimeError(
                "Qdrant Server no responde en "
                f"{SETTINGS.qdrant_url}."
            )

        return "local"

    def _server_available(self) -> bool:
        try:
            request = urllib.request.Request(
                SETTINGS.qdrant_url,
                method="GET",
            )
            with urllib.request.urlopen(
                request,
                timeout=2,
            ) as response:
                return 200 <= response.status < 300
        except (
            OSError,
            urllib.error.URLError,
            urllib.error.HTTPError,
        ):
            return False

    def _create_client(
        self,
        path: str | Path,
    ) -> QdrantClient:
        if self.connection_mode == "server":
            return QdrantClient(
                url=SETTINGS.qdrant_url,
                timeout=SETTINGS.qdrant_timeout_seconds,
            )

        return QdrantClient(path=str(path))

    def status(self) -> dict:
        info = self.client.get_collection(
            self.collection_name
        )
        points_count = getattr(info, "points_count", 0) or 0

        return {
            "mode": self.connection_mode,
            "url": (
                SETTINGS.qdrant_url
                if self.connection_mode == "server"
                else str(SETTINGS.vector_path)
            ),
            "collection": self.collection_name,
            "points": int(points_count),
        }

    def _ensure_collection(self) -> None:
        if self.client.collection_exists(self.collection_name):
            return
        dimension = self.embedding_service.dimension()
        self.client.create_collection(
            collection_name=self.collection_name,
            vectors_config=models.VectorParams(
                size=dimension,
                distance=models.Distance.COSINE,
            ),
        )

    def _upsert_points_in_batches(
        self,
        points,
        wait: bool = True,
    ) -> None:
        """Envia puntos en bloques pequenos con reintentos idempotentes."""
        batch_size = max(
            1,
            int(getattr(SETTINGS, "qdrant_upsert_batch_size", 256)),
        )
        retries = max(
            1,
            int(getattr(SETTINGS, "qdrant_upsert_retries", 3)),
        )
        for start in range(0, len(points), batch_size):
            batch = points[start:start + batch_size]
            last_error = None
            for attempt in range(1, retries + 1):
                try:
                    self.client.upsert(
                        collection_name=self.collection_name,
                        points=batch,
                        wait=wait,
                    )
                    last_error = None
                    break
                except Exception as error:
                    last_error = error
                    if attempt >= retries:
                        break
                    time.sleep(min(8, 2 ** (attempt - 1)))
            if last_error is not None:
                raise last_error

    def replace_documents_batch(
        self,
        documents: list[Document],
        wait: bool = True,
    ) -> dict[str, int]:
        """Reemplaza varios documentos con un solo lote de embeddings y upsert."""
        usable = [
            document
            for document in documents
            if document.fragments
        ]

        for document in documents:
            self.delete_document(
                document.path,
                wait=False,
            )

        if not usable:
            return {
                str(document.path.resolve()): 0
                for document in documents
            }

        fragments = [
            (document, fragment)
            for document in usable
            for fragment in document.fragments
        ]

        vectors = self.embedding_service.embed_passages(
            fragment.text
            for _, fragment in fragments
        )

        points = [
            models.PointStruct(
                id=str(
                    uuid5(
                        NAMESPACE_URL,
                        (
                            f"{document.path.resolve()}"
                            f"::{fragment.index}"
                        ),
                    )
                ),
                vector=vector.tolist(),
                payload={
                    "document_name": document.name,
                    "document_path": str(
                        document.path.resolve()
                    ),
                    "category": document.category,
                    "fragment_index": fragment.index,
                    "text": fragment.text,
                    "start_char": fragment.start_char,
                    "end_char": fragment.end_char,
                    "page_start": fragment.page_start,
                    "page_end": fragment.page_end,
                    "metadata": document.metadata,
                },
            )
            for (document, fragment), vector
            in zip(fragments, vectors)
        ]

        self._upsert_points_in_batches(points, wait=wait)

        counts = {
            str(document.path.resolve()): 0
            for document in documents
        }

        for document, _ in fragments:
            key = str(document.path.resolve())
            counts[key] += 1

        return counts

    def replace_document(self, document: Document) -> int:
        self.delete_document(document.path)

        if not document.fragments:
            return 0

        vectors = self.embedding_service.embed_passages(
            fragment.text for fragment in document.fragments
        )

        points = [
            models.PointStruct(
                id=str(
                    uuid5(
                        NAMESPACE_URL,
                        f"{document.path.resolve()}::{fragment.index}",
                    )
                ),
                vector=vector.tolist(),
                payload={
                    "document_name": document.name,
                    "document_path": str(document.path.resolve()),
                    "category": document.category,
                    "fragment_index": fragment.index,
                    "text": fragment.text,
                    "start_char": fragment.start_char,
                    "end_char": fragment.end_char,
                    "page_start": fragment.page_start,
                    "page_end": fragment.page_end,
                    "metadata": document.metadata,
                },
            )
            for fragment, vector in zip(document.fragments, vectors)
        ]

        self._upsert_points_in_batches(points, wait=True)

        return len(points)

    def delete_document(
        self,
        document_path: str | Path,
        wait: bool = True,
    ) -> None:
        self.client.delete(
            collection_name=self.collection_name,
            points_selector=models.FilterSelector(
                filter=models.Filter(
                    must=[
                        models.FieldCondition(
                            key="document_path",
                            match=models.MatchValue(
                                value=str(Path(document_path).resolve())
                            ),
                        )
                    ]
                )
            ),
            wait=wait,
        )


    # >>> LEXIA VECTOR RELOCATION FILTER INDEX 1.0
    def relocate_document(
        self,
        old_path: str | Path,
        new_path: str | Path,
        document_name: str,
        category: str,
        metadata: dict | None = None,
    ) -> int:
        old_value = str(Path(old_path).resolve())
        new_value = str(Path(new_path).resolve())

        if not getattr(
            self,
            "_lexia_document_path_payload_index_ready",
            False,
        ):
            info = self.client.get_collection(
                collection_name=self.collection_name
            )
            payload_schema = getattr(info, "payload_schema", {}) or {}

            if "document_path" not in payload_schema:
                self.client.create_payload_index(
                    collection_name=self.collection_name,
                    field_name="document_path",
                    field_schema=models.PayloadSchemaType.KEYWORD,
                    wait=True,
                )

            self._lexia_document_path_payload_index_ready = True

        self.client.set_payload(
            collection_name=self.collection_name,
            payload={
                "document_path": new_value,
                "document_name": document_name,
                "category": category,
                "metadata": metadata or {},
            },
            points=models.Filter(
                must=[
                    models.FieldCondition(
                        key="document_path",
                        match=models.MatchValue(value=old_value),
                    )
                ]
            ),
            wait=False,
        )
        return 1
    # <<< LEXIA VECTOR RELOCATION FILTER INDEX 1.0

    # >>> LEXIA VECTOR RELOCATION BATCH 1.0
    # >>> LEXIA VECTOR RELOCATION BULK ID 1.0
    def relocate_documents(
        self,
        relocations,
        lookup_batch_size: int = 128,
        update_batch_size: int = 256,
    ) -> int:
        items = list(relocations or [])
        if not items:
            return 0

        if not getattr(
            self,
            "_lexia_document_path_payload_index_ready",
            False,
        ):
            info = self.client.get_collection(
                collection_name=self.collection_name
            )
            payload_schema = getattr(info, "payload_schema", {}) or {}

            if "document_path" not in payload_schema:
                self.client.create_payload_index(
                    collection_name=self.collection_name,
                    field_name="document_path",
                    field_schema=models.PayloadSchemaType.KEYWORD,
                    wait=True,
                )

            self._lexia_document_path_payload_index_ready = True

        normalized = []
        item_by_old = {}

        for item in items:
            old_value = str(Path(item["old_path"]).resolve())
            new_value = str(Path(item["new_path"]).resolve())

            normalized_item = {
                "old_path": old_value,
                "new_path": new_value,
                "name": item.get("name") or "",
                "category": item.get("category") or "Sin categoría",
                "metadata": item.get("metadata") or {},
            }
            normalized.append(normalized_item)
            item_by_old[old_value] = normalized_item

        point_ids_by_old = {
            old_path: []
            for old_path in item_by_old
        }

        lookup_size = max(1, int(lookup_batch_size))
        old_paths = list(item_by_old)

        for start in range(0, len(old_paths), lookup_size):
            path_chunk = old_paths[start:start + lookup_size]
            offset = None

            while True:
                records, offset = self.client.scroll(
                    collection_name=self.collection_name,
                    scroll_filter=models.Filter(
                        must=[
                            models.FieldCondition(
                                key="document_path",
                                match=models.MatchAny(
                                    any=path_chunk
                                ),
                            )
                        ]
                    ),
                    limit=2048,
                    offset=offset,
                    with_payload=["document_path"],
                    with_vectors=False,
                )

                for record in records:
                    payload = record.payload or {}
                    old_value = str(
                        payload.get("document_path") or ""
                    )
                    if old_value in point_ids_by_old:
                        point_ids_by_old[old_value].append(record.id)

                if offset is None:
                    break

        missing = [
            old_path
            for old_path, point_ids in point_ids_by_old.items()
            if not point_ids
        ]
        if missing:
            preview = ", ".join(missing[:5])
            raise RuntimeError(
                "Qdrant sin puntos para "
                f"{len(missing)}/{len(items)} relocalizaciones. "
                f"Ejemplos: {preview}"
            )

        operations = []

        for item in normalized:
            point_ids = point_ids_by_old[item["old_path"]]
            operations.append(
                models.SetPayloadOperation(
                    set_payload=models.SetPayload(
                        payload={
                            "document_path": item["new_path"],
                            "document_name": item["name"],
                            "category": item["category"],
                            "metadata": item["metadata"],
                        },
                        points=point_ids,
                    )
                )
            )

        update_size = max(1, int(update_batch_size))

        for start in range(0, len(operations), update_size):
            self.client.batch_update_points(
                collection_name=self.collection_name,
                update_operations=operations[
                    start:start + update_size
                ],
                wait=False,
            )

        return len(items)
    # <<< LEXIA VECTOR RELOCATION BULK ID 1.0
    def update_document_metadata(
        self,
        document_path: str | Path,
        document_name: str,
        category: str,
        metadata: dict,
    ) -> int:
        """Actualiza clasificación y metadatos sin recalcular vectores."""
        path_value = str(Path(document_path).resolve())
        point_ids = []
        offset = None

        while True:
            records, offset = self.client.scroll(
                collection_name=self.collection_name,
                scroll_filter=models.Filter(
                    must=[
                        models.FieldCondition(
                            key="document_path",
                            match=models.MatchValue(
                                value=path_value
                            ),
                        )
                    ]
                ),
                limit=256,
                offset=offset,
                with_payload=False,
                with_vectors=False,
            )
            point_ids.extend(
                record.id for record in records
            )

            if offset is None:
                break

        if not point_ids:
            return 0

        self.client.set_payload(
            collection_name=self.collection_name,
            payload={
                "document_name": document_name,
                "category": category,
                "metadata": metadata,
            },
            points=point_ids,
            wait=True,
        )
        return len(point_ids)

    # >>> LEXIA VECTOR PATH INDIRECTION 1.0
    def _resolve_current_document_path(
        self,
        stored_path: str | Path,
    ) -> Path:
        path_value = str(stored_path)

        try:
            with sqlite3.connect(SETTINGS.catalog_path) as connection:
                row = connection.execute(
                    """
                    SELECT current_location.path
                    FROM document_locations AS historical
                    JOIN document_locations AS current_location
                      ON current_location.content_hash = historical.content_hash
                     AND current_location.is_current <> 0
                    JOIN documents AS d
                      ON d.path = current_location.path
                     AND d.is_deleted = 0
                    WHERE historical.path = ?
                    ORDER BY current_location.last_seen_at DESC
                    LIMIT 1
                    """,
                    (path_value,),
                ).fetchone()

            if row and row[0]:
                return Path(str(row[0]))
        except sqlite3.Error:
            pass

        return Path(path_value)
    # <<< LEXIA VECTOR PATH INDIRECTION 1.0

    def search(
        self,
        query: str,
        limit: int,
        category: str | None = None,
    ) -> list[SearchResult]:
        query_filter = None

        if category:
            query_filter = models.Filter(
                must=[
                    models.FieldCondition(
                        key="category",
                        match=models.MatchValue(value=category),
                    )
                ]
            )

        response = self.client.query_points(
            collection_name=self.collection_name,
            query=self.embedding_service.embed_query(query).tolist(),
            query_filter=query_filter,
            limit=limit,
            with_payload=True,
        )

        results: list[SearchResult] = []

        for position, point in enumerate(response.points, start=1):
            payload = point.payload or {}
            results.append(
                SearchResult(
                    document_name=str(payload.get("document_name", "")),
                    document_path=self._resolve_current_document_path(
                        str(payload.get("document_path", ""))
                    ),
                    category=str(payload.get("category", "")),
                    fragment_index=int(payload.get("fragment_index", 0)),
                    text=str(payload.get("text", "")),
                    score=float(point.score),
                    semantic_rank=position,
                    page_start=payload.get("page_start"),
                    page_end=payload.get("page_end"),
                )
            )

        return results
