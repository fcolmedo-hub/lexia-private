from datetime import datetime
import threading
from pathlib import Path

from config.settings import SETTINGS
from core.pipeline import DocumentPipeline
from core.ocr_service import OCRService
from storage.ocr_queue_repository import (
    OCRQueueRepository,
)
from storage.search_cache_repository import (
    SearchCacheRepository,
)


class OCRQueueService:
    def __init__(self, indexer):
        self._indexer_source = indexer
        self.repository = OCRQueueRepository(
            SETTINGS.ocr_queue_path
        )
        self.recovered_interrupted = self.repository.recover_interrupted()
        self._lock = threading.RLock()
        self._running = False
        self._cancel_requested = threading.Event()
        self._active_queue_path = ""
        self._state = {
            "running": False,
            "current_file": "",
            "processed": 0,
            "total": 0,
            "error": "",
            "stopping": False,
            "stage": "idle",
            "document_name": "",
            "current_page": 0,
            "completed_pages": 0,
            "total_pages": 0,
            "last_finished_at": "",
            "progress_error": "",
        }

    @property
    def indexer(self):
        source = self._indexer_source
        return source() if callable(source) else source

    def list_pending(self) -> list[dict]:
        return self.repository.list_pending()

    def discard_stale_errors(self) -> int:
        """Remove OCR errors for entries that no longer belong to this library."""
        removed = 0
        for item in self.repository.list_pending():
            if str(item.get("status") or "").casefold() != "error":
                continue
            path = str(item.get("document_path") or "")
            error = str(item.get("error") or "").casefold()
            if (
                not Path(path).is_file()
                or "detector no encontró el archivo dentro de la biblioteca" in error
            ):
                if self.repository.remove(path):
                    removed += 1
        return removed

    def stats(self) -> dict:
        return self.repository.stats()

    def state(self) -> dict:
        return dict(self._state)

    def _publish_page_progress(self, page: int, total: int) -> None:
        """Publish and persist the real PDF page currently being scanned."""
        total_pages = max(0, int(total or 0))
        current_page = max(0, int(page or 0))
        if total_pages:
            current_page = min(total_pages, current_page)
        self._state.update(
            current_page=current_page,
            completed_pages=max(0, current_page - 1),
            total_pages=total_pages,
            progress_error="",
        )
        if self._active_queue_path:
            try:
                self.repository.update_progress(
                    self._active_queue_path,
                    current_page,
                )
            except Exception as error:
                self._state["progress_error"] = str(error)

    def request_stop(self) -> bool:
        with self._lock:
            if not self._running:
                return False
            self._cancel_requested.set()
            self._state["stopping"] = True
            OCRService.cancel_all()
            try:
                self.indexer.request_stop()
            except Exception:
                pass
            return True

    def set_selected(
        self,
        path: str,
        selected: bool,
    ) -> None:
        self.repository.set_selected(
            path,
            selected,
        )

    def select_all(self, selected: bool) -> None:
        self.repository.select_all(selected)

    def start_selected(self) -> bool:
        with self._lock:
            if self._running or self.repository.stats().get("processing", 0):
                return False

            paths = self.repository.get_selected_paths()
            if not paths:
                return False

            self._running = True
            self._cancel_requested.clear()
            thread = threading.Thread(
                target=self._process,
                args=(paths,),
                name="LexIA-OCR-Queue",
                daemon=True,
            )
            thread.start()
            return True

    def _process(self, paths: list[str]) -> None:
        self._state = {
            "running": True,
            "current_file": "",
            "processed": 0,
            "total": len(paths),
            "error": "",
            "stopping": False,
            "stage": "ocr",
            "document_name": "",
            "current_page": 0,
            "completed_pages": 0,
            "total_pages": 0,
            "last_finished_at": "",
            "progress_error": "",
        }

        try:
            for position, path in enumerate(
                paths,
                start=1,
            ):
                if self._cancel_requested.is_set():
                    break
                # A moved or deleted document cannot be OCR-processed. It is
                # stale queue state, not an error that needs user attention.
                if not Path(path).is_file():
                    self.repository.remove(path)
                    self._state.update(
                        current_file=str(path),
                        document_name=Path(path).name,
                        stage="skipped",
                        error="",
                        processed=position,
                    )
                    continue
                queue_item = self.repository.get(path) or {}
                total_pages = int(queue_item.get("total_pages", 0) or 0)
                self._active_queue_path = path
                self._state.update(
                    current_file=str(path),
                    processed=position - 1,
                    document_name=str(
                        queue_item.get("document_name")
                        or Path(path).name
                    ),
                    current_page=1 if total_pages else 0,
                    completed_pages=0,
                    total_pages=total_pages,
                )
                self.repository.mark_processing(path)

                try:
                    # >>> LEXIA OCR STABLE INDEXER INSTANCE FIX 1.0
                    indexer = self.indexer

                    self._state["stage"] = "ocr"
                    pipeline = DocumentPipeline().run(
                        changed_paths=[path],
                        full_scan=False,
                        force_ocr_paths=[path],
                        cancel_callback=self._cancel_requested.is_set,
                        ocr_progress_callback=self._publish_page_progress,
                    )
                    state = indexer.catalog.get_file_state(path)
                    if pipeline.detected != 1:
                        # The document is no longer part of the active
                        # library tree. Drop its stale OCR entry quietly.
                        self.repository.remove(path)
                        self._state.update(stage="skipped", error="")
                        self._state["processed"] = position
                        continue
                    if pipeline.failed:
                        detail = (
                            str((state or {}).get("extraction_error") or "")
                            or "La extracción u OCR terminó con error."
                        )
                        raise RuntimeError(
                            f"OCR no pudo procesar '{Path(path).name}': {detail}"
                        )

                    if state is None:
                        raise RuntimeError(
                            "La extraccion termino sin guardar el documento."
                        )
                    if state.get("extraction_error"):
                        raise RuntimeError(str(state["extraction_error"]))
                    if not str(state.get("text_content") or "").strip():
                        raise RuntimeError(
                            "La extraccion termino sin texto utilizable."
                        )

                    # >>> LEXIA OCR DIAGNOSTIC PROBE 1.0
                    probe_path = Path("runtime") / "ocr_diagnostic.log"

                    def _probe(message: str) -> None:
                        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
                        with probe_path.open("a", encoding="utf-8") as probe_file:
                            probe_file.write(f"{timestamp} | {message}\n")

                    _probe(
                        "POST_PIPELINE | "
                        f"path={path} | "
                        f"content_hash={state.get('content_hash')} | "
                        f"vector_indexed_hash={state.get('vector_indexed_hash')} | "
                        f"extraction_method={state.get('extraction_method')} | "
                        f"extraction_error={state.get('extraction_error')}"
                    )

                    pending_before = indexer.catalog.pending_vector_documents(
                        paths=[path]
                    )
                    _probe(
                        "PRE_INDEXER | "
                        f"path={path} | "
                        f"pending_count={len(pending_before)} | "
                        f"pending_hashes={[doc.content_hash for doc in pending_before]}"
                    )
                    # <<< LEXIA OCR DIAGNOSTIC PROBE 1.0

                    self._state["stage"] = "indexing"
                    index_result = indexer.run(
                        deleted_paths=pipeline.deleted_paths,
                        target_paths=[path],
                    )

                    # >>> LEXIA OCR DIAGNOSTIC PROBE 1.0
                    _probe(
                        "INDEX_RESULT | "
                        f"path={path} | "
                        f"documents_indexed={index_result.documents_indexed} | "
                        f"fragments_indexed={index_result.fragments_indexed} | "
                        f"documents_deleted={index_result.documents_deleted} | "
                        f"documents_relocated={index_result.documents_relocated} | "
                        f"cancelled={index_result.cancelled}"
                    )
                    # <<< LEXIA OCR DIAGNOSTIC PROBE 1.0

                    if index_result.cancelled:
                        raise RuntimeError("La indexacion fue cancelada.")

                    # >>> LEXIA OCR TRUST INDEX RESULT FIX 1.0
                    # VectorIndexer.run() es sincrono. Si retorna sin
                    # excepcion y no fue cancelado, la indexacion vectorial
                    # termino. mark_vector_indexed() ya valida internamente
                    # que su confirmacion haya quedado persistida.
                    if index_result.documents_indexed < 1:
                        raise RuntimeError(
                            "La indexacion no proceso el documento OCR."
                        )
                    # <<< LEXIA OCR TRUST INDEX RESULT FIX 1.0

                    self.repository.mark_completed(path)
                    SearchCacheRepository(
                        SETTINGS.search_cache_path
                    ).clear()

                except Exception as error:
                    if self._cancel_requested.is_set():
                        self.repository.mark_pending(path)
                        break
                    else:
                        self.repository.mark_error(
                            path,
                            str(error),
                        )

                self._state["processed"] = position

        except Exception as error:
            self._state["error"] = str(error)

        finally:
            # Keep the last file/page visible after short OCR jobs. Otherwise
            # the UI can miss the complete operation between two polls.
            final_stage = (
                "stopped"
                if self._cancel_requested.is_set()
                else "error"
                if self._state.get("error")
                else "completed"
                if self._state.get("document_name")
                else "idle"
            )
            self._state.update(
                running=False,
                stopping=False,
                stage=final_stage,
                last_finished_at=datetime.now().isoformat(timespec="seconds"),
            )
            self._active_queue_path = ""
            self._running = False
            self._cancel_requested.clear()
