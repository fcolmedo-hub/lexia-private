import argparse

from config.settings import SETTINGS
from core.pipeline import DocumentPipeline
from search.embedding_service import EmbeddingService
from search.indexer import VectorIndexer
from search.cached_search import CachedSearchEngine
from search.professional_search import (
    ProfessionalLegalSearchEngine,
)
from search.vector_store import VectorStore
from storage.catalog import DocumentCatalog
from storage.search_feedback_repository import (
    SearchFeedbackRepository,
)


def services():
    catalog = DocumentCatalog(SETTINGS.catalog_path)
    embeddings = EmbeddingService()
    vector_store = VectorStore(embeddings)
    feedback = SearchFeedbackRepository(
        SETTINGS.feedback_path
    )

    return (
        catalog,
        vector_store,
        ProfessionalLegalSearchEngine(
            vector_store,
            catalog,
            feedback,
        ),
        VectorIndexer(catalog, vector_store),
    )


def command_ingest() -> None:
    def progress(done: int, total: int, path: str) -> None:
        print(
            f"\rProcesando {done}/{total}: "
            f"{path[:80]:<80}",
            end="",
            flush=True,
        )

    pipeline = DocumentPipeline().run(
        progress_callback=progress
    )
    print()

    _, _, _, indexer = services()
    indexed = indexer.run(pipeline.deleted_paths)
    SearchCacheRepository(SETTINGS.search_cache_path).clear()

    print("\nLEXIA PROFESSIONAL 1.0 - INGESTA\n")
    print(f"Detectados            : {pipeline.detected}")
    print(f"Nuevos                : {pipeline.new}")
    print(f"Modificados            : {pipeline.modified}")
    print(f"Sin cambios            : {pipeline.skipped}")
    print(f"Duplicados             : {pipeline.duplicates}")
    print(f"Documentos con OCR     : {pipeline.ocr_documents}")
    print(f"Páginas con OCR        : {pipeline.ocr_pages}")
    print(f"Sin texto              : {pipeline.without_text}")
    print(f"Errores                : {pipeline.failed}")
    print(f"Documentos indexados   : {indexed.documents_indexed}")
    print(f"Fragmentos indexados   : {indexed.fragments_indexed}")
    print(f"Trabajo de ingesta     : {pipeline.job_id}")


def command_search(
    query: str,
    category: str | None,
    limit: int,
) -> None:
    _, _, engine, _ = services()

    results = engine.search(
        query=query,
        category=category,
        limit=limit,
    )

    for number, result in enumerate(results, start=1):
        print("\n" + "=" * 80)
        print(
            f"{number}. {result.document_name} | "
            f"{result.category} | {result.page_label} | "
            f"{result.score:.5f}"
        )
        print(result.document_path)
        print("-" * 80)
        print(result.text[:1200])


def main() -> None:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command")

    subparsers.add_parser("ingest")

    search = subparsers.add_parser("search")
    search.add_argument("query")
    search.add_argument("--category")
    search.add_argument("--limit", type=int, default=10)

    args = parser.parse_args()

    if args.command == "ingest":
        command_ingest()
    elif args.command == "search":
        command_search(
            args.query,
            args.category,
            args.limit,
        )
    else:
        print(
            "Usá: python main.py ingest, "
            "python main.py search \"consulta\" "
            "o python run_lexia.py"
        )


if __name__ == "__main__":
    main()
