from dataclasses import dataclass
import threading
from pathlib import Path
from typing import Callable

from storage.catalog import DocumentCatalog
from search.vector_store import VectorStore


@dataclass(slots=True)
class IndexResult:
    documents_indexed: int
    fragments_indexed: int
    documents_deleted: int
    documents_relocated: int = 0
    cancelled: bool = False


class VectorIndexer:
    def __init__(self, catalog: DocumentCatalog, vector_store: VectorStore):
        self.catalog = catalog
        self.vector_store = vector_store
        self._cancel_requested = threading.Event()

    def request_stop(self) -> None:
        self._cancel_requested.set()

    def cancellation_requested(self) -> bool:
        return self._cancel_requested.is_set()

    def run(
        self,
        deleted_paths: list[str] | None = None,
        progress_callback: Callable[[int, int, str], None] | None = None,
        target_paths: list[str] | None = None,
    ) -> IndexResult:
        self._cancel_requested.clear()
        relocated = 0
        target_set = {
            str(Path(path).resolve())
            for path in (target_paths or [])
        }
        relocations = self.catalog.pending_vector_relocations()
        if target_set:
            relocations = [
                item for item in relocations
                if str(Path(item["new_path"]).resolve())
                in target_set
            ]
        # >>> LEXIA VECTOR RELOCATION BATCH INTEGRATION 1.0
        # >>> LEXIA VECTOR RELOCATION BYPASS 1.0
        # Un movimiento fisico no modifica embeddings.
        # Qdrant conserva la ruta historica y Search resuelve la actual.
        # >>> LEXIA VECTOR RELOCATION COMPLETION BATCH 1.0
        if relocations:
            relocation_ids = [item["id"] for item in relocations]
            self.catalog.complete_vector_relocations(relocation_ids)
            relocated += len(relocations)
        # <<< LEXIA VECTOR RELOCATION COMPLETION BATCH 1.0
        # <<< LEXIA VECTOR RELOCATION BYPASS 1.0
        if target_paths:
            pending = self.catalog.pending_vector_documents(
                paths=target_paths
            )
        else:
            pending = self.catalog.pending_vector_documents()
        total = len(pending)
        documents_indexed = 0
        fragments_indexed = 0

        batch_size = max(
            1,
            int(
                getattr(
                    __import__(
                        "config.settings",
                        fromlist=["SETTINGS"],
                    ).SETTINGS,
                    "vector_document_batch_size",
                    8,
                )
            ),
        )

        for batch_start in range(0, total, batch_size):
            if self._cancel_requested.is_set():
                break
            batch = pending[
                batch_start:batch_start + batch_size
            ]

            if progress_callback and batch:
                progress_callback(
                    batch_start,
                    total,
                    str(batch[0].path),
                )

            if hasattr(
                self.vector_store,
                "replace_documents_batch",
            ):
                counts = (
                    self.vector_store.replace_documents_batch(
                        batch,
                        wait=True,
                    )
                )
            else:
                counts = {
                    str(document.path.resolve()):
                    self.vector_store.replace_document(
                        document
                    )
                    for document in batch
                }

            for document in batch:
                fragments_indexed += int(
                    counts.get(
                        str(document.path.resolve()),
                        0,
                    )
                )
                self.catalog.mark_vector_indexed(
                    document.path,
                    document.content_hash,
                )
                documents_indexed += 1

            if progress_callback and batch:
                done = min(
                    batch_start + len(batch),
                    total,
                )
                progress_callback(
                    done,
                    total,
                    str(batch[-1].path),
                )

        paths = deleted_paths or []
        for path in paths:
            self.vector_store.delete_document(path)

        cancelled = self._cancel_requested.is_set()
        if progress_callback:
            progress_callback(
                documents_indexed if cancelled else total,
                total,
                "Detenido" if cancelled else "Completado",
            )

        return IndexResult(
            documents_indexed=documents_indexed,
            fragments_indexed=fragments_indexed,
            documents_deleted=len(paths),
            documents_relocated=relocated,
            cancelled=cancelled,
        )

