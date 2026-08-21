from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from config.settings import SETTINGS


@dataclass(frozen=True, slots=True)
class StructuralClassification:
    category: str
    levels: tuple[str, ...]
    classification_1: str | None = None
    classification_2: str | None = None
    classification_3: str | None = None
    classification_4: str | None = None


def _project_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _library_root() -> Path:
    root = Path(SETTINGS.library_path)
    if not root.is_absolute():
        root = (_project_root() / root).resolve()
    return root.resolve()


def classify_structural_path(
    path: str | Path,
    library_root: str | Path | None = None,
) -> StructuralClassification:
    """
    Clasificación estructural autoritativa.

    La categoría es el primer directorio bajo la biblioteca.
    Los cuatro niveles siguientes son classification_1..4.

    El contenido del documento NO interviene.
    """
    absolute = Path(path).resolve()
    if library_root is None:
        library = _library_root()
    else:
        root = Path(library_root)
        if not root.is_absolute():
            root = (_project_root() / root).resolve()
        library = root.resolve()

    try:
        relative = absolute.relative_to(library)
    except ValueError as exc:
        raise ValueError(
            f"El documento está fuera de la biblioteca configurada: {absolute}"
        ) from exc

    parts = relative.parts
    if len(parts) < 2:
        raise ValueError(
            "El documento debe estar dentro de una categoría física de la biblioteca."
        )

    category = parts[0]
    levels = tuple(parts[1:-1])
    padded = list(levels[:4]) + [None] * 4

    return StructuralClassification(
        category=category,
        levels=levels,
        classification_1=padded[0],
        classification_2=padded[1],
        classification_3=padded[2],
        classification_4=padded[3],
    )
