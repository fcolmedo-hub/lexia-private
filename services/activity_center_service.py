import sqlite3
from dataclasses import dataclass
from pathlib import Path

from config.settings import SETTINGS


@dataclass(slots=True)
class ActivitySnapshot:
    documents_total: int
    sync_phase: str
    sync_status: str
    sync_current_file: str
    sync_processed: int
    sync_total: int
    sync_percentage: int
    sync_last_error: str
    sync_last_time: str
    ocr_pending: int
    ocr_processing: int
    ocr_errors: int
    ocr_running: bool
    ocr_current_file: str
    ocr_processed: int
    ocr_total: int
    recent_documents: list[dict]
    recent_errors: list[dict]

    @property
    def busy(self) -> bool:
        return (
            self.sync_phase
            in {"waiting", "scanning", "indexing", "knowledge"}
            or self.ocr_running
        )

    @property
    def headline(self) -> str:
        if self.ocr_running:
            return "OCR en ejecución"

        if self.sync_phase == "indexing":
            return "Indexando documentos"

        if self.sync_phase == "scanning":
            return "Comprobando biblioteca"

        if self.sync_phase == "waiting":
            return "Preparando actualización"

        if self.sync_phase == "error":
            return "La sincronización requiere atención"

        if self.ocr_errors:
            return "Hay documentos OCR con error"

        if self.ocr_pending:
            return "Biblioteca disponible con OCR pendiente"

        return "Biblioteca al día"


class ActivityCenterService:
    def __init__(
        self,
        autosync,
        ocr_queue,
        catalog_path: str | Path | None = None,
    ):
        self.autosync = autosync
        self.ocr_queue = ocr_queue
        self.catalog_path = Path(
            catalog_path or SETTINGS.catalog_path
        )

    def snapshot(
        self,
        recent_limit: int = 8,
        error_limit: int = 8,
    ) -> ActivitySnapshot:
        sync_state = self.autosync.state()
        ocr_state = self.ocr_queue.state()
        ocr_stats = self.ocr_queue.stats()

        documents_total = self._documents_total()

        return ActivitySnapshot(
            documents_total=documents_total,
            sync_phase=str(
                sync_state.get("phase", "idle")
            ),
            sync_status=str(
                sync_state.get("status", "Listo")
            ),
            sync_current_file=str(
                sync_state.get("current_file", "")
            ),
            sync_processed=int(
                sync_state.get("processed", 0) or 0
            ),
            sync_total=int(
                sync_state.get("total", 0) or 0
            ),
            sync_percentage=int(
                sync_state.get("percentage", 0) or 0
            ),
            sync_last_error=str(
                sync_state.get("last_error", "") or ""
            ),
            sync_last_time=str(
                sync_state.get("last_sync", "") or ""
            ),
            ocr_pending=int(
                ocr_stats.get("pending", 0) or 0
            ),
            ocr_processing=int(
                ocr_stats.get("processing", 0) or 0
            ),
            ocr_errors=int(
                ocr_stats.get("error", 0) or 0
            ),
            ocr_running=bool(
                ocr_state.get("running", False)
            ),
            ocr_current_file=str(
                ocr_state.get("current_file", "")
            ),
            ocr_processed=int(
                ocr_state.get("processed", 0) or 0
            ),
            ocr_total=int(
                ocr_state.get("total", 0) or 0
            ),
            recent_documents=self._recent_documents(
                recent_limit
            ),
            recent_errors=self._recent_errors(
                error_limit
            ),
        )

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(
            self.catalog_path,
            timeout=15,
        )
        connection.row_factory = sqlite3.Row
        return connection

    def _documents_total(self) -> int:
        if not self.catalog_path.exists():
            return 0

        try:
            with self._connect() as connection:
                return int(
                    connection.execute(
                        """
                        SELECT COUNT(*) AS total
                        FROM documents
                        WHERE is_deleted = 0
                        """
                    ).fetchone()["total"]
                )
        except sqlite3.Error:
            return 0

    def _recent_documents(
        self,
        limit: int,
    ) -> list[dict]:
        if limit <= 0 or not self.catalog_path.exists():
            return []

        try:
            with self._connect() as connection:
                rows = connection.execute(
                    """
                    SELECT
                        name,
                        path,
                        category,
                        extraction_method,
                        total_pages,
                        updated_at,
                        duplicate_of,
                        extraction_error
                    FROM documents
                    WHERE is_deleted = 0
                      AND (
                          extraction_error IS NULL
                          OR extraction_error = ''
                      )
                    ORDER BY updated_at DESC
                    LIMIT ?
                    """,
                    (limit,),
                ).fetchall()

            return [dict(row) for row in rows]

        except sqlite3.Error:
            return []

    def _recent_errors(
        self,
        limit: int,
    ) -> list[dict]:
        if limit <= 0:
            return []

        errors: list[dict] = []

        if self.catalog_path.exists():
            try:
                with self._connect() as connection:
                    rows = connection.execute(
                        """
                        SELECT
                            name,
                            path,
                            extraction_error AS error,
                            updated_at,
                            'indexación' AS source
                        FROM documents
                        WHERE is_deleted = 0
                          AND extraction_error IS NOT NULL
                          AND extraction_error != ''
                        ORDER BY updated_at DESC
                        LIMIT ?
                        """,
                        (limit,),
                    ).fetchall()

                errors.extend(dict(row) for row in rows)

            except sqlite3.Error:
                pass

        try:
            for row in self.ocr_queue.list_pending():
                if row.get("status") != "error":
                    continue

                errors.append(
                    {
                        "name": row.get(
                            "document_name",
                            Path(
                                row.get(
                                    "document_path",
                                    "",
                                )
                            ).name,
                        ),
                        "path": row.get(
                            "document_path",
                            "",
                        ),
                        "error": row.get(
                            "error",
                            "",
                        ),
                        "updated_at": row.get(
                            "updated_at",
                            "",
                        ),
                        "source": "OCR",
                    }
                )
        except Exception:
            pass

        errors.sort(
            key=lambda row: row.get(
                "updated_at",
                "",
            ),
            reverse=True,
        )
        return errors[:limit]
