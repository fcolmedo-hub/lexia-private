import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable

from config.settings import SETTINGS
from core.document_chunker import DocumentChunker
from core.document_classifier import (
    DeterministicDocumentClassifier,
)
from core.document_detector import DocumentDetector
from core.document_extractor import (
    DocumentExtractionError,
    DocumentExtractor,
)
from core.duplicate_detector import DuplicateDetector
from core.file_hasher import FileHasher
from legal.metadata_extractor import LegalMetadataExtractor
from storage.catalog import DocumentCatalog
from storage.ingestion_job_repository import (
    IngestionJobRepository,
)
from storage.ocr_queue_repository import OCRQueueRepository
from services.rejected_document_service import (
    RejectedDocumentService,
)


@dataclass(slots=True)
class PipelineResult:
    detected: int
    new: int
    modified: int
    skipped: int
    duplicates: int
    relocated: int
    classified: int
    ocr_documents: int
    ocr_pages: int
    without_text: int
    failed: int
    deleted_paths: list[str]
    generated_fragments: int
    job_id: int


class PipelineCancelled(RuntimeError):
    pass


class DocumentPipeline:
    def __init__(
        self,
        library_path: str | Path = SETTINGS.library_path,
        catalog_path: str | Path = SETTINGS.catalog_path,
        jobs_path: str | Path = SETTINGS.jobs_path,
    ):
        self.detector = DocumentDetector(library_path)
        self.extractor = DocumentExtractor()
        self.classifier = DeterministicDocumentClassifier()
        self.chunker = DocumentChunker(
            chunk_size=SETTINGS.chunk_size,
            overlap=SETTINGS.chunk_overlap,
        )
        self.metadata_extractor = LegalMetadataExtractor()
        self.hasher = FileHasher()
        self.catalog = DocumentCatalog(catalog_path)
        self.duplicates = DuplicateDetector(self.catalog)
        self.jobs = IngestionJobRepository(jobs_path)
        self.ocr_queue = OCRQueueRepository(
            SETTINGS.ocr_queue_path
        )
        self.logger = logging.getLogger(__name__)
        self.rejected_documents = RejectedDocumentService()

    def run(
        self,
        progress_callback: (
            Callable[[int, int, str], None] | None
        ) = None,
        changed_paths: Iterable[str | Path] | None = None,
        full_scan: bool = True,
        deleted_paths: Iterable[str | Path] | None = None,
        force_ocr_paths: Iterable[str | Path] | None = None,
        force_reprocess_paths: Iterable[str | Path] | None = None,
        cancel_callback: Callable[[], bool] | None = None,
        ocr_progress_callback: (
            Callable[[int, int], None] | None
        ) = None,
    ) -> PipelineResult:
        force_ocr = {
            str(Path(path).resolve())
            for path in (force_ocr_paths or ())
        }
        force_reprocess = {
            str(Path(path).resolve())
            for path in (force_reprocess_paths or ())
        }

        documents = self.detector.scan(
            paths=changed_paths,
            progress_callback=None,
        )

        if full_scan:
            active_paths = self.detector.all_active_paths()
        else:
            active_paths = set()

        job_id = self.jobs.create(len(documents))

        stats = {
            "new": 0,
            "modified": 0,
            "skipped": 0,
            "duplicates": 0,
            "relocated": 0,
            "classified": 0,
            "ocr_documents": 0,
            "ocr_pages": 0,
            "without_text": 0,
            "failed": 0,
            "rejected": 0,
            "generated_fragments": 0,
        }

        try:
            for position, document in enumerate(
                documents,
                start=1,
            ):
                if cancel_callback and cancel_callback():
                    raise PipelineCancelled("Procesamiento detenido por el usuario.")
                if progress_callback:
                    progress_callback(
                        position - 1,
                        len(documents),
                        str(document.path),
                    )

                self._process_document(
                    document,
                    stats,
                    active_paths,
                    force_ocr=(
                        str(document.path.resolve())
                        in force_ocr
                    ),
                    force_reprocess=(
                        str(document.path.resolve())
                        in force_reprocess
                    ),
                    cancel_callback=cancel_callback,
                    ocr_progress_callback=ocr_progress_callback,
                )

                if progress_callback:
                    progress_callback(
                        position,
                        len(documents),
                        str(document.path),
                    )

                if (
                    position
                    % SETTINGS.checkpoint_every_documents
                    == 0
                    or position == len(documents)
                ):
                    self.jobs.checkpoint(
                        job_id,
                        position,
                        str(document.path),
                        stats,
                    )

            removed: list[str] = []

            if full_scan:
                removed = self.catalog.mark_missing_as_deleted(
                    active_paths
                )
            else:
                removed = self.catalog.mark_paths_deleted(
                    {
                        str(Path(path).resolve())
                        for path in (deleted_paths or ())
                    }
                )

            self.jobs.finish(
                job_id,
                "completed",
                stats,
            )

            if progress_callback:
                progress_callback(
                    len(documents),
                    len(documents),
                    "Completado",
                )

        except KeyboardInterrupt:
            self.jobs.finish(
                job_id,
                "interrupted",
                stats,
            )
            raise

        except Exception:
            self.jobs.finish(
                job_id,
                "failed",
                stats,
            )
            raise

        return PipelineResult(
            detected=len(documents),
            new=stats["new"],
            modified=stats["modified"],
            skipped=stats["skipped"],
            duplicates=stats["duplicates"],
            relocated=stats["relocated"],
            classified=stats["classified"],
            ocr_documents=stats["ocr_documents"],
            ocr_pages=stats["ocr_pages"],
            without_text=stats["without_text"],
            failed=stats["failed"],
            deleted_paths=removed,
            generated_fragments=stats[
                "generated_fragments"
            ],
            job_id=job_id,
        )

    @staticmethod
    def _state_is_complete(state: dict | None) -> bool:
        if not state:
            return False
        if bool(state.get("is_deleted")):
            return False
        if state.get("extraction_error"):
            return False
        if state.get("duplicate_of"):
            return True
        method = str(state.get("extraction_method") or "").strip()
        category = str(state.get("category") or "").strip()
        text_content = str(state.get("text_content") or "").strip()
        if method in {"duplicate", "ocr_pending"}:
            return True
        if text_content and method:
            return True
        if category == "Sin texto" and method:
            return True
        return False

    def _process_document(
        self,
        document,
        stats: dict,
        active_paths: set[str],
        force_ocr: bool = False,
        force_reprocess: bool = False,
        cancel_callback: Callable[[], bool] | None = None,
        ocr_progress_callback: (
            Callable[[int, int], None] | None
        ) = None,
    ) -> None:
        previous = self.catalog.get_file_state(
            document.path
        )

        # Fast path: no hash, no PDF open, no OCR.
        if (
            not force_ocr
            and not force_reprocess
            and previous
            and self._state_is_complete(previous)
            and int(previous["size"]) == document.size
            and int(previous["modified_ns"])
            == document.modified_ns
        ):
            stats["skipped"] += 1
            return

        document.content_hash = self.hasher.calculate(
            document.path
        )
        previous_hash = (
            previous["content_hash"]
            if previous
            else None
        )

        if (
            not force_ocr
            and not force_reprocess
            and previous_hash == document.content_hash
            and previous
            and self._state_is_complete(previous)
        ):
            stats["skipped"] += 1
            return

        if previous is None:
            relocation = self.catalog.find_relocation_candidate(
                document.content_hash,
                active_paths,
                document.path,
            )

            if relocation and self.catalog.relocate_document(
                relocation,
                document,
            ):
                stats["relocated"] += 1
                return

            stats["new"] += 1
        else:
            stats["modified"] += 1

        duplicate_of = self.duplicates.find_original(
            document.content_hash,
            document.path,
        )

        if duplicate_of:
            document.duplicate_of = duplicate_of
            document.extraction_method = "duplicate"
            document.metadata = {
                "physical_folder": (
                    document.physical_folder
                ),
                "classification": {
                    "document_type": "Duplicado",
                    "confidence": 1.0,
                    "reasons": [
                        "Contenido idéntico a otro documento"
                    ],
                },
            }
            stats["duplicates"] += 1
            self.catalog.save(document)
            return

        if force_ocr and document.has_text:
            self.ocr_queue.mark_completed(
                str(document.path.resolve())
            )
            return

        try:
            def ocr_progress(page, total):
                self.ocr_queue.update_progress(
                    str(document.path.resolve()),
                    page,
                )
                if ocr_progress_callback:
                    ocr_progress_callback(page, total)
                if cancel_callback and cancel_callback():
                    raise PipelineCancelled(
                        "OCR detenido por el usuario."
                    )

            extraction = self.extractor.extract(
                document.path,
                allow_ocr=force_ocr,
                progress_callback=(
                    ocr_progress
                    if force_ocr
                    else None
                ),
            )
            document.text = extraction.text
            document.extraction_method = extraction.method
            document.total_pages = extraction.total_pages
            document.ocr_pages = extraction.ocr_pages

            if document.ocr_pages:
                stats["ocr_documents"] += 1
                stats["ocr_pages"] += (
                    document.ocr_pages
                )

            partial_ocr = False

            if extraction.needs_ocr:
                min_chars = int(
                    getattr(
                        SETTINGS,
                        "ocr_partial_index_min_chars",
                        2000,
                    )
                )

                if len(document.text.strip()) < min_chars:
                    # OCR is an operational state, never a library category.
                    # Preserve the physical category so the navigator remains
                    # an exact representation of the user's folder tree.
                    from services.structural_category_policy import (
                        classify_structural_path,
                    )
                    structural = classify_structural_path(
                        document.path,
                        library_root=self.detector.library_path,
                    )
                    document.category = structural.category
                    document.metadata = {
                        "physical_folder": (
                            document.physical_folder
                        ),
                        "classification": {
                            "document_type": "OCR pendiente",
                            "confidence": 1.0,
                            "reasons": [
                                "PDF con texto insuficiente para indexación parcial"
                            ],
                        },
                        "ocr_pending": True,
                        "ocr_partial_indexed": False,
                        "ocr_text_chars": len(document.text.strip()),
                    }
                    document.fragments = []
                    self.ocr_queue.enqueue(
                        str(document.path.resolve()),
                        document.name,
                        document.total_pages,
                    )
                    stats["without_text"] += 1
                    self.catalog.save(document)
                    return

                partial_ocr = True
                document.extraction_method = "ocr_partial_pending"
                self.ocr_queue.enqueue(
                    str(document.path.resolve()),
                    document.name,
                    document.total_pages,
                )

            if document.has_text:
                classification = self.classifier.classify(
                    document.text,
                    document.path,
                )
                # Structural Category Authority 1.0:
                # la ruta física manda sobre la clasificación semántica.
                from services.structural_category_policy import (
                    classify_structural_path,
                )
                structural = classify_structural_path(
                    document.path,
                    library_root=self.detector.library_path,
                )
                document.category = structural.category
                document.classification_confidence = (
                    classification.confidence
                )
                document.classification_reasons = (
                    classification.reasons
                )

                legal_metadata = (
                    self.metadata_extractor.extract(
                        document.text,
                        document.path,
                        document.category,
                    )
                )

                document.metadata = {
                    **legal_metadata,
                    "physical_folder": (
                        document.physical_folder
                    ),
                    "classification": {
                        "document_type": (
                            classification.document_type
                        ),
                        "subtype": classification.subtype,
                        "confidence": (
                            classification.confidence
                        ),
                        "reasons": (
                            classification.reasons
                        ),
                        "authority": (
                            classification.detected_authority
                        ),
                        "jurisdiction": (
                            classification.detected_jurisdiction
                        ),
                    },
                }

                if partial_ocr:
                    document.metadata["ocr_pending"] = True
                    document.metadata["ocr_partial_indexed"] = True
                    document.metadata["ocr_text_chars"] = len(
                        document.text.strip()
                    )

                document.fragments = self.chunker.split(
                    document
                )
                stats["generated_fragments"] += (
                    document.fragment_count
                )
                stats["classified"] += 1
            else:
                document.category = "Sin texto"
                document.metadata = {
                    "physical_folder": (
                        document.physical_folder
                    ),
                    "classification": {
                        "document_type": "Sin texto",
                        "confidence": 1.0,
                        "reasons": [
                            "No se pudo obtener texto utilizable"
                        ],
                    },
                }
                stats["without_text"] += 1

        except DocumentExtractionError as error:
            document.extraction_error = str(error)
            document.category = "Error de extracción"
            stats["failed"] += 1

            rejected = None
            if getattr(SETTINGS, "rejected_documents_enabled", True):
                try:
                    rejected = self.rejected_documents.inspect_and_quarantine(document.path)
                except Exception as quarantine_error:
                    self.logger.error(
                        "No se pudo apartar %s: %s",
                        document.path,
                        quarantine_error,
                    )

            if rejected is not None:
                stats["rejected"] += 1
                active_paths.discard(str(document.path.resolve()))
                self.logger.warning(
                    "Documento rechazado movido: %s -> %s | %s",
                    rejected.source_path,
                    rejected.destination_path,
                    rejected.reason,
                )
                return

            self.logger.error("%s | Ruta: %s", error, document.path.resolve())

        self.catalog.save(document)
