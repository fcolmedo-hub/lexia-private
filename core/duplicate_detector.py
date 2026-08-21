from pathlib import Path

from storage.catalog import DocumentCatalog


class DuplicateDetector:
    def __init__(self, catalog: DocumentCatalog):
        self.catalog = catalog

    def find_original(
        self,
        content_hash: str,
        current_path: str | Path,
    ) -> str | None:
        return self.catalog.find_path_by_hash(
            content_hash,
            exclude_path=str(Path(current_path).resolve()),
        )
