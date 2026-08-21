import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path

from config.settings import SETTINGS
from core.document_chunker import DocumentChunker
from core.document_classifier import DeterministicDocumentClassifier
from legal.metadata_extractor import LegalMetadataExtractor
from models.document import Document
from storage.catalog import DocumentCatalog

@dataclass(slots=True)
class OCRRecoveryResult:
    examined: int = 0
    recovered: int = 0
    skipped_short_text: int = 0
    missing_files: int = 0
    errors: int = 0
    fragments_generated: int = 0

class OCRPendingRecoveryService:
    def __init__(self, catalog_path=None, min_chars=None):
        self.catalog_path = Path(catalog_path or SETTINGS.catalog_path)
        self.catalog = DocumentCatalog(self.catalog_path)
        self.chunker = DocumentChunker(
            chunk_size=SETTINGS.chunk_size,
            overlap=SETTINGS.chunk_overlap,
        )
        self.classifier = DeterministicDocumentClassifier()
        self.metadata_extractor = LegalMetadataExtractor()
        self.min_chars = int(
            min_chars if min_chars is not None
            else getattr(SETTINGS, "ocr_partial_index_min_chars", 2000)
        )

    def candidates(self):
        con = sqlite3.connect(self.catalog_path)
        con.row_factory = sqlite3.Row
        try:
            rows = con.execute("""
                SELECT * FROM documents
                WHERE is_deleted = 0
                  AND duplicate_of IS NULL
                  AND extraction_error IS NULL
                  AND extraction_method = 'ocr_pending'
                  AND LENGTH(TRIM(text_content)) > 0
                ORDER BY path
            """).fetchall()
            return [dict(r) for r in rows]
        finally:
            con.close()

    def run(self):
        result = OCRRecoveryResult()
        rows = self.candidates()
        result.examined = len(rows)

        for row in rows:
            try:
                text = (row.get("text_content") or "").strip()
                if len(text) < self.min_chars:
                    result.skipped_short_text += 1
                    continue

                path = Path(row["path"])
                if not path.exists():
                    result.missing_files += 1
                    continue

                doc = Document(
                    name=row["name"],
                    path=path,
                    category=row["category"],
                    extension=row["extension"],
                    size=int(row["size"]),
                    modified_ns=int(row["modified_ns"]),
                    content_hash=row["content_hash"],
                    text=text,
                    extraction_error=None,
                    metadata=json.loads(row.get("metadata_json") or "{}"),
                    extraction_method="ocr_partial_pending",
                    ocr_pages=int(row.get("ocr_pages") or 0),
                    total_pages=row.get("total_pages"),
                    duplicate_of=None,
                )

                c = self.classifier.classify(doc.text, doc.path)
                # Structural Category Authority 1.0:
                # la categoría proviene exclusivamente del árbol físico.
                from services.structural_category_policy import (
                    classify_structural_path,
                )
                structural = classify_structural_path(doc.path)
                doc.category = structural.category
                legal = self.metadata_extractor.extract(
                    doc.text, doc.path, doc.category
                )
                doc.metadata = {
                    **legal,
                    "physical_folder": doc.physical_folder,
                    "classification": {
                        "document_type": c.document_type,
                        "subtype": c.subtype,
                        "confidence": c.confidence,
                        "reasons": c.reasons,
                        "authority": c.detected_authority,
                        "jurisdiction": c.detected_jurisdiction,
                    },
                    "ocr_pending": True,
                    "ocr_partial_indexed": True,
                    "ocr_text_chars": len(text),
                    "ocr_recovered_from_pending": True,
                }
                doc.fragments = self.chunker.split(doc)
                self.catalog.save(doc)
                result.fragments_generated += doc.fragment_count
                result.recovered += 1
            except Exception:
                result.errors += 1
        return result
