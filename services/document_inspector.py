import json
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path

from qdrant_client import models

from config.settings import SETTINGS


@dataclass(slots=True)
class DocumentInspection:
    path: str
    name: str
    category: str
    extension: str
    size: int
    content_hash: str
    vector_indexed_hash: str
    text_chars: int
    fragment_count: int
    vector_count: int
    extraction_method: str
    extraction_error: str
    ocr_pages: int
    total_pages: int | None
    duplicate_of: str
    is_deleted: bool
    updated_at: str
    metadata: dict = field(default_factory=dict)
    knowledge: dict = field(default_factory=dict)

    @property
    def exists_on_disk(self) -> bool:
        return Path(self.path).exists()

    @property
    def text_extracted(self) -> bool:
        return self.text_chars > 0 and not self.extraction_error

    @property
    def catalog_indexed(self) -> bool:
        return not self.is_deleted

    @property
    def vectors_expected(self) -> bool:
        return not bool(self.duplicate_of) and self.fragment_count > 0

    @property
    def vector_indexed(self) -> bool:
        if self.duplicate_of:
            return True

        return (
            self.vector_count > 0
            and self.vector_indexed_hash == self.content_hash
        )

    @property
    def knowledge_indexed(self) -> bool:
        return bool(self.knowledge)

    @property
    def searchable(self) -> bool:
        return (
            self.catalog_indexed
            and self.text_extracted
            and (
                self.vector_indexed
                or self.fragment_count > 0
            )
        )

    @property
    def context_ready(self) -> bool:
        return self.searchable

    @property
    def overall_status(self) -> str:
        if self.extraction_error:
            return "Error de extracción"

        if self.is_deleted:
            return "Marcado como eliminado"

        if self.duplicate_of:
            return "Duplicado registrado"

        if not self.text_extracted:
            return "Sin texto extraído"

        if not self.vector_indexed:
            return "Pendiente de indexación vectorial"

        if not self.knowledge_indexed:
            return "Indexado; Knowledge Engine pendiente"

        return "Correcto"

    def status_rows(self) -> list[dict]:
        return [
            {
                "componente": "Archivo en disco",
                "correcto": self.exists_on_disk,
                "detalle": self.path,
            },
            {
                "componente": "Catálogo",
                "correcto": self.catalog_indexed,
                "detalle": self.updated_at,
            },
            {
                "componente": "Texto extraído",
                "correcto": self.text_extracted,
                "detalle": (
                    f"{self.text_chars:,} caracteres · "
                    f"{self.extraction_method}"
                ),
            },
            {
                "componente": "Fragmentación",
                "correcto": (
                    self.fragment_count > 0
                    or bool(self.duplicate_of)
                ),
                "detalle": (
                    f"{self.fragment_count} fragmentos"
                    if not self.duplicate_of
                    else f"Copia de {self.duplicate_of}"
                ),
            },
            {
                "componente": "Qdrant / vectores",
                "correcto": self.vector_indexed,
                "detalle": (
                    f"{self.vector_count} vectores"
                    if not self.duplicate_of
                    else "Utiliza el documento original"
                ),
            },
            {
                "componente": "Knowledge Engine",
                "correcto": self.knowledge_indexed,
                "detalle": (
                    f"{len(self.knowledge.get('concepts', []))} conceptos"
                    if self.knowledge_indexed
                    else "Pendiente o no instalado"
                ),
            },
            {
                "componente": "Disponible para búsqueda",
                "correcto": self.searchable,
                "detalle": (
                    "Sí" if self.searchable else "No"
                ),
            },
            {
                "componente": "Disponible para Context Builder",
                "correcto": self.context_ready,
                "detalle": (
                    "Sí" if self.context_ready else "No"
                ),
            },
        ]


class DocumentInspector:
    def __init__(
        self,
        vector_store=None,
        catalog_path: str | Path | None = None,
        knowledge_path: str | Path | None = None,
    ):
        self.catalog_path = Path(
            catalog_path or SETTINGS.catalog_path
        )
        self.knowledge_path = Path(
            knowledge_path
            or getattr(
                SETTINGS,
                "knowledge_path",
                Path("runtime/knowledge.sqlite3"),
            )
        )
        self.vector_store = vector_store

    def search(
        self,
        term: str,
        limit: int = 25,
    ) -> list[dict]:
        clean = term.strip()

        if not clean:
            return []

        pattern = f"%{clean}%"

        with self._catalog_connection() as connection:
            rows = connection.execute(
                """
                SELECT
                    path, name, category, extension, size,
                    content_hash, vector_indexed_hash,
                    extraction_method, extraction_error,
                    ocr_pages, total_pages, duplicate_of,
                    is_deleted, updated_at,
                    LENGTH(text_content) AS text_chars,
                    (
                        SELECT COUNT(*)
                        FROM fragments f
                        WHERE f.document_path = documents.path
                    ) AS fragment_count
                FROM documents
                WHERE name LIKE ? COLLATE NOCASE
                   OR path LIKE ? COLLATE NOCASE
                ORDER BY
                    CASE
                        WHEN name = ? COLLATE NOCASE THEN 0
                        WHEN name LIKE ? COLLATE NOCASE THEN 1
                        ELSE 2
                    END,
                    is_deleted,
                    name
                LIMIT ?
                """,
                (
                    pattern,
                    pattern,
                    clean,
                    f"{clean}%",
                    limit,
                ),
            ).fetchall()

        return [dict(row) for row in rows]

    def inspect(self, document_path: str) -> DocumentInspection:
        resolved = str(Path(document_path).resolve())

        with self._catalog_connection() as connection:
            row = connection.execute(
                """
                SELECT
                    path, name, category, extension, size,
                    content_hash, vector_indexed_hash,
                    extraction_method, extraction_error,
                    ocr_pages, total_pages, duplicate_of,
                    is_deleted, updated_at,
                    metadata_json,
                    LENGTH(text_content) AS text_chars,
                    (
                        SELECT COUNT(*)
                        FROM fragments f
                        WHERE f.document_path = documents.path
                    ) AS fragment_count
                FROM documents
                WHERE path = ?
                """,
                (resolved,),
            ).fetchone()

        if not row:
            raise LookupError(
                "El documento no existe en el catálogo de LexIA."
            )

        data = dict(row)
        metadata = self._decode_json(
            data.pop("metadata_json", "{}")
        )
        knowledge = self._knowledge_for_path(resolved)
        vector_count = self._vector_count(resolved)

        return DocumentInspection(
            path=data["path"],
            name=data["name"],
            category=data["category"],
            extension=data["extension"],
            size=int(data["size"] or 0),
            content_hash=data["content_hash"] or "",
            vector_indexed_hash=(
                data["vector_indexed_hash"] or ""
            ),
            text_chars=int(data["text_chars"] or 0),
            fragment_count=int(
                data["fragment_count"] or 0
            ),
            vector_count=vector_count,
            extraction_method=(
                data["extraction_method"] or ""
            ),
            extraction_error=(
                data["extraction_error"] or ""
            ),
            ocr_pages=int(data["ocr_pages"] or 0),
            total_pages=data["total_pages"],
            duplicate_of=data["duplicate_of"] or "",
            is_deleted=bool(data["is_deleted"]),
            updated_at=data["updated_at"] or "",
            metadata=metadata,
            knowledge=knowledge,
        )

    def inspect_by_term(
        self,
        term: str,
    ) -> DocumentInspection:
        matches = self.search(term, limit=2)

        if not matches:
            raise LookupError(
                f"No se encontró ningún documento que coincida con "
                f"'{term}'."
            )

        if len(matches) > 1:
            raise LookupError(
                "La búsqueda coincide con más de un documento. "
                "Usá un nombre más específico o la ruta completa."
            )

        return self.inspect(matches[0]["path"])

    def _vector_count(self, path: str) -> int:
        if self.vector_store is None:
            return -1

        try:
            response = self.vector_store.client.count(
                collection_name=(
                    self.vector_store.collection_name
                ),
                count_filter=models.Filter(
                    must=[
                        models.FieldCondition(
                            key="document_path",
                            match=models.MatchValue(
                                value=path,
                            ),
                        )
                    ]
                ),
                exact=True,
            )
            return int(response.count)

        except Exception:
            return -1

    def _knowledge_for_path(self, path: str) -> dict:
        if not self.knowledge_path.exists():
            return {}

        try:
            connection = sqlite3.connect(
                self.knowledge_path
            )
            connection.row_factory = sqlite3.Row

            try:
                row = connection.execute(
                    """
                    SELECT *
                    FROM knowledge_documents
                    WHERE document_path = ?
                    """,
                    (path,),
                ).fetchone()

                if not row:
                    return {}

                result = dict(row)

                tables = {
                    item["name"]
                    for item in connection.execute(
                        """
                        SELECT name FROM sqlite_master
                        WHERE type = 'table'
                        """
                    ).fetchall()
                }

                concepts = []

                if {
                    "document_concepts",
                    "concepts",
                }.issubset(tables):
                    concepts = [
                        item["name"]
                        for item in connection.execute(
                            """
                            SELECT c.name
                            FROM document_concepts dc
                            JOIN concepts c
                              ON c.id = dc.concept_id
                            WHERE dc.document_path = ?
                            ORDER BY dc.weight DESC, c.name
                            """,
                            (path,),
                        ).fetchall()
                    ]

                citations = []

                if "document_citations" in tables:
                    citations = [
                        item["citation"]
                        for item in connection.execute(
                            """
                            SELECT citation
                            FROM document_citations
                            WHERE document_path = ?
                            ORDER BY citation
                            """,
                            (path,),
                        ).fetchall()
                    ]

                result["concepts"] = concepts
                result["citations"] = citations
                result["parties"] = self._decode_json(
                    result.get("parties_json", "[]")
                )
                result["keywords"] = self._decode_json(
                    result.get("keywords_json", "[]")
                )
                return result

            finally:
                connection.close()

        except sqlite3.Error:
            return {}

    def _catalog_connection(self) -> sqlite3.Connection:
        connection = sqlite3.connect(
            self.catalog_path
        )
        connection.row_factory = sqlite3.Row
        return connection

    def _decode_json(self, value):
        if isinstance(value, (dict, list)):
            return value

        try:
            return json.loads(value or "{}")
        except (TypeError, json.JSONDecodeError):
            return {}
