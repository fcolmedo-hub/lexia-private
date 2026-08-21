from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from services.rejected_initial_scan_service import (
    RejectedInitialScanService,
)


def progress(
    current: int,
    total: int,
    path: str,
) -> None:
    if (
        current == 0
        or current == total
        or current % 500 == 0
    ):
        print(
            f"Revisados: {current}/{total}"
            + (
                f" | {Path(path).name}"
                if path
                else ""
            )
        )


def main() -> int:
    service = RejectedInitialScanService()
    result = service.run_once(
        progress_callback=progress
    )

    if result.skipped:
        print(
            "La revisión inicial de documentos inválidos "
            "ya fue realizada anteriormente."
        )
        print(f"Marca: {result.marker_path}")
        return 0

    print()
    print("Revisión inicial finalizada.")
    print(f"PDF revisados: {result.scanned}")
    print(f"PDF válidos: {result.valid}")
    print(f"PDF rechazados: {result.rejected}")
    print(f"Errores de lectura: {result.errors}")
    print(f"Marca: {result.marker_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
