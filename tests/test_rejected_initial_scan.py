from pathlib import Path

import fitz

from services.rejected_document_service import (
    RejectedDocumentService,
)
from services.rejected_initial_scan_service import (
    RejectedInitialScanService,
)


def test_initial_scan_runs_only_once(
    tmp_path: Path,
) -> None:
    library = tmp_path / "data"
    library.mkdir()

    invalid = library / "invalido.pdf"
    invalid.write_text(
        "<html><body>Error</body></html>",
        encoding="utf-8",
    )

    valid = library / "valido.pdf"
    document = fitz.open()
    document.new_page()
    document.save(valid)
    document.close()

    rejected_root = tmp_path / "Rejected Documents"
    marker = tmp_path / "runtime" / "done.json"

    service = RejectedInitialScanService(
        library_path=library,
        marker_path=marker,
        rejected_service=RejectedDocumentService(
            rejected_root
        ),
    )

    first = service.run_once()
    second = service.run_once()

    assert first.skipped is False
    assert first.scanned == 2
    assert first.rejected == 1
    assert first.valid == 1
    assert marker.exists()
    assert not invalid.exists()
    assert valid.exists()

    assert second.skipped is True
    assert second.scanned == 0


def test_force_allows_manual_repeat(
    tmp_path: Path,
) -> None:
    library = tmp_path / "data"
    library.mkdir()

    marker = tmp_path / "runtime" / "done.json"

    service = RejectedInitialScanService(
        library_path=library,
        marker_path=marker,
        rejected_service=RejectedDocumentService(
            tmp_path / "Rejected Documents"
        ),
    )

    first = service.run_once()
    forced = service.run_once(force=True)

    assert first.skipped is False
    assert forced.skipped is False
