from __future__ import annotations

import argparse
from dataclasses import asdict
from pathlib import Path

from config.settings import SETTINGS
from core.document_extractor import DocumentExtractor
from core.pipeline import DocumentPipeline
from search.embedding_service import EmbeddingService
from search.indexer import VectorIndexer
from search.vector_store import VectorStore
from storage.catalog import DocumentCatalog
from storage.ocr_queue_repository import OCRQueueRepository


def candidates(repository) -> list[dict]:
    extractor = DocumentExtractor()
    result = []
    for item in repository.list_pending():
        path = Path(item["document_path"])
        if not path.is_file():
            continue
        try:
            extraction = extractor.extract(path, allow_ocr=False)
        except Exception:
            continue
        if extraction.text.strip() and not extraction.needs_ocr:
            result.append({**item, "text_chars": len(extraction.text.strip())})
    return result


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Reconcilia falsos OCR pendientes causados por paginas en blanco."
    )
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    repository = OCRQueueRepository(SETTINGS.ocr_queue_path)
    found = candidates(repository)
    print(f"Falsos OCR pendientes detectados: {len(found)}")
    for item in found:
        print(f"- {item['document_path']} ({item['text_chars']} caracteres)")
    if not args.apply or not found:
        if found:
            print("\nPara reconciliarlos ejecuta nuevamente con --apply")
        return 0

    catalog = DocumentCatalog(SETTINGS.catalog_path)
    indexer = VectorIndexer(catalog, VectorStore(EmbeddingService()))
    completed = errors = 0
    for position, item in enumerate(found, start=1):
        path = Path(item["document_path"]).resolve()
        print(f"[{position}/{len(found)}] Reconciliando {path}")
        try:
            pipeline = DocumentPipeline().run(
                changed_paths=[path], full_scan=False, force_ocr_paths=[path]
            )
            if pipeline.detected != 1 or pipeline.failed:
                raise RuntimeError(f"Pipeline invalido: {asdict(pipeline)}")
            indexer.run(
                deleted_paths=pipeline.deleted_paths,
                target_paths=[str(path)],
            )
            state = catalog.get_file_state(path)
            if (
                state is None
                or not state.get("content_hash")
                or state.get("content_hash") != state.get("vector_indexed_hash")
            ):
                raise RuntimeError("Hash vectorial no confirmado")
            repository.mark_completed(str(path))
            completed += 1
        except Exception as error:
            repository.mark_error(str(path), str(error))
            errors += 1
            print(f"  ERROR: {error}")
    print(f"Completados: {completed} | Errores: {errors}")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
