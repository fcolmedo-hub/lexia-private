from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable

from config.settings import SETTINGS
from services.rejected_document_service import (
    RejectedDocumentService,
)


@dataclass(frozen=True, slots=True)
class InitialRejectedScanResult:
    scanned: int
    rejected: int
    valid: int
    errors: int
    skipped: bool
    marker_path: Path


class RejectedInitialScanService:
    """
    Barrido único de PDFs existentes antes de Sprint D.

    Después de completarse, deja una marca persistente y no vuelve
    a ejecutarse automáticamente.
    """

    def __init__(
        self,
        library_path: str | Path | None = None,
        marker_path: str | Path | None = None,
        rejected_service: RejectedDocumentService | None = None,
    ):
        self.library_path = Path(
            library_path or SETTINGS.library_path
        ).resolve()
        self.marker_path = Path(
            marker_path
            or (
                SETTINGS.runtime_path
                / "rejected_initial_scan_done.json"
            )
        ).resolve()
        self.rejected_service = (
            rejected_service
            or RejectedDocumentService()
        )

    def is_done(self) -> bool:
        if not self.marker_path.exists():
            return False

        try:
            data = json.loads(
                self.marker_path.read_text(
                    encoding="utf-8"
                )
            )
        except Exception:
            return False

        return bool(data.get("completed"))

    def run_once(
        self,
        progress_callback: (
            Callable[[int, int, str], None] | None
        ) = None,
        force: bool = False,
    ) -> InitialRejectedScanResult:
        if self.is_done() and not force:
            return InitialRejectedScanResult(
                scanned=0,
                rejected=0,
                valid=0,
                errors=0,
                skipped=True,
                marker_path=self.marker_path,
            )

        pdf_paths = sorted(
            (
                path
                for path in self.library_path.rglob("*")
                if path.is_file()
                and path.suffix.lower() == ".pdf"
            ),
            key=lambda item: str(item).lower(),
        )

        scanned = 0
        rejected = 0
        valid = 0
        errors = 0
        total = len(pdf_paths)

        for position, path in enumerate(
            pdf_paths,
            start=1,
        ):
            if progress_callback:
                progress_callback(
                    position - 1,
                    total,
                    str(path),
                )

            try:
                result = (
                    self.rejected_service
                    .inspect_and_quarantine(path)
                )
            except Exception:
                errors += 1
            else:
                if result is None:
                    valid += 1
                else:
                    rejected += 1

            scanned += 1

            if progress_callback:
                progress_callback(
                    position,
                    total,
                    str(path),
                )

        self.marker_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )
        self.marker_path.write_text(
            json.dumps(
                {
                    "completed": True,
                    "completed_at": datetime.now().isoformat(
                        timespec="seconds"
                    ),
                    "library_path": str(self.library_path),
                    "scanned": scanned,
                    "rejected": rejected,
                    "valid": valid,
                    "errors": errors,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

        return InitialRejectedScanResult(
            scanned=scanned,
            rejected=rejected,
            valid=valid,
            errors=errors,
            skipped=False,
            marker_path=self.marker_path,
        )
