import argparse

from services.backup_service import BackupService
from services.runtime_guard import RuntimeGuard


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("backup_path")
    args = parser.parse_args()

    guard = RuntimeGuard()
    guard.clear_stale()

    if guard.read_state():
        raise RuntimeError(
            "Cerrá LexIA antes de restaurar una copia."
        )

    BackupService().restore(args.backup_path)
    print("Copia restaurada correctamente.")
    print(
        "Ejecutá luego: python .\\ingest_lexia.py "
        "para reconstruir el índice si fuera necesario."
    )


if __name__ == "__main__":
    main()
