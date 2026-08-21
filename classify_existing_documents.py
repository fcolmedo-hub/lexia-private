import json
import sqlite3
from pathlib import Path

from config.settings import SETTINGS
from core.document_classifier import (
    DeterministicDocumentClassifier,
)
from services.application import LexIAApplication
from storage.catalog import DocumentCatalog


def main() -> None:
    classifier = DeterministicDocumentClassifier()
    catalog = DocumentCatalog(
        SETTINGS.catalog_path
    )
    app = LexIAApplication()

    connection = sqlite3.connect(
        SETTINGS.catalog_path
    )
    connection.row_factory = sqlite3.Row

    try:
        rows = connection.execute(
            """
            SELECT
                path,
                name,
                text_content,
                metadata_json,
                is_deleted,
                duplicate_of
            FROM documents
            WHERE is_deleted = 0
              AND duplicate_of IS NULL
              AND text_content != ''
            ORDER BY path
            """
        ).fetchall()
    finally:
        connection.close()

    total = len(rows)
    updated = 0
    errors = 0

    for position, row in enumerate(
        rows,
        start=1,
    ):
        print(
            f"\rClasificando {position}/{total}: "
            f"{row['name'][:70]:<70}",
            end="",
            flush=True,
        )

        try:
            classification = classifier.classify(
                row["text_content"],
                row["path"],
            )

            try:
                metadata = json.loads(
                    row["metadata_json"] or "{}"
                )
            except json.JSONDecodeError:
                metadata = {}

            metadata["classification"] = {
                "document_type": (
                    classification.document_type
                ),
                "subtype": classification.subtype,
                "confidence": (
                    classification.confidence
                ),
                "reasons": classification.reasons,
                "authority": (
                    classification.detected_authority
                ),
                "jurisdiction": (
                    classification.detected_jurisdiction
                ),
            }
            metadata.setdefault(
                "physical_folder",
                str(
                    Path(row["path"])
                    .resolve()
                    .parent
                ),
            )

            catalog.update_classification(
                row["path"],
                classification.document_type,
                metadata,
            )

            app.vector_store.update_document_metadata(
                row["path"],
                row["name"],
                classification.document_type,
                metadata,
            )
            updated += 1

        except Exception as error:
            errors += 1
            print(
                f"\nError en {row['name']}: {error}"
            )

    print()
    print("\nDOCUMENT CLASSIFIER 2.0\n")
    print(f"Documentos analizados : {total}")
    print(f"Clasificados          : {updated}")
    print(f"Errores               : {errors}")
    print(
        "\nNo se recalcularon embeddings."
    )


if __name__ == "__main__":
    main()
