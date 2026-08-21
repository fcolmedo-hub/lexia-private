import os
from pathlib import Path


def open_file(file_path: str | Path) -> None:
    path = Path(file_path)

    if not path.exists():
        raise FileNotFoundError(f"No existe el archivo: {path}")

    os.startfile(path)
