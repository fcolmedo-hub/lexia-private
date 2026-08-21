from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path

DEFAULT_CATEGORY_ALIASES = {
    "escritos": "Escritos",
    "doctrina": "Doctrina",
    "jurisprudencia": "Jurisprudencia",
    "legislacion": "Legislación",
    "legislación": "Legislación",
}

@dataclass(frozen=True)
class LibraryClassification:
    absolute_path: str
    relative_path: str
    category_folder: str
    category: str
    levels: tuple[str, ...]
    classification_1: str | None
    classification_2: str | None
    classification_3: str | None
    classification_4: str | None
    extra_levels: tuple[str, ...]
    valid: bool
    reason: str = ""

    def as_dict(self):
        return {
            "absolute_path": self.absolute_path,
            "relative_path": self.relative_path,
            "category_folder": self.category_folder,
            "category": self.category,
            "levels": list(self.levels),
            "classification_1": self.classification_1,
            "classification_2": self.classification_2,
            "classification_3": self.classification_3,
            "classification_4": self.classification_4,
            "extra_levels": list(self.extra_levels),
            "valid": self.valid,
            "reason": self.reason,
        }

class LibraryClassificationTree:
    def __init__(self, library_root, category_aliases=None):
        self.library_root = Path(library_root).resolve()
        aliases = category_aliases or DEFAULT_CATEGORY_ALIASES
        self.category_aliases = {
            str(k).strip().casefold(): str(v).strip()
            for k, v in aliases.items()
        }

    def classify(self, path):
        absolute = Path(path).resolve()
        try:
            relative = absolute.relative_to(self.library_root)
        except ValueError:
            return LibraryClassification(
                str(absolute), "", "", "Fuera de biblioteca", (),
                None, None, None, None, (), False,
                "La ruta no está dentro de library_root."
            )
        parts = relative.parts
        if len(parts) < 2:
            return LibraryClassification(
                str(absolute), relative.as_posix(),
                parts[0] if parts else "", "Sin categoría", (),
                None, None, None, None, (), False,
                "El archivo debe estar dentro de una carpeta de categoría."
            )
        category_folder = parts[0]
        category = self.category_aliases.get(
            category_folder.casefold(), category_folder
        )
        levels = tuple(parts[1:-1])
        def level(i):
            return levels[i] if i < len(levels) else None
        return LibraryClassification(
            str(absolute), relative.as_posix(), category_folder, category,
            levels, level(0), level(1), level(2), level(3),
            levels[4:], True, ""
        )

    def list_tree(self):
        if not self.library_root.exists():
            return {}
        return {
            p.name: self._folder_node(p)
            for p in sorted(
                (x for x in self.library_root.iterdir() if x.is_dir()),
                key=lambda x: x.name.casefold()
            )
        }

    def _folder_node(self, folder):
        try:
            dirs = sorted(
                (x for x in folder.iterdir() if x.is_dir()),
                key=lambda x: x.name.casefold()
            )
        except OSError:
            dirs = []
        return {p.name: self._folder_node(p) for p in dirs}

    def destination(self, category_folder, levels=()):
        parts = [self._safe_part(category_folder)]
        parts.extend(self._safe_part(v) for v in levels if str(v).strip())
        destination = self.library_root.joinpath(*parts).resolve()
        destination.relative_to(self.library_root)
        return destination

    @staticmethod
    def _safe_part(value):
        value = str(value or "").strip()
        if not value or value in {".", ".."} or "/" in value or "\\" in value:
            raise ValueError("Nombre de carpeta inválido.")
        return value
