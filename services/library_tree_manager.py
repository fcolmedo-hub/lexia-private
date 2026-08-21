from pathlib import Path

class LibraryTreeManager:
    ROOT_CATEGORIES = ("Escritos", "Doctrina", "Jurisprudencia", "Legislacion")

    def __init__(self, library_root):
        self.library_root = Path(library_root).resolve()

    @staticmethod
    def _safe_part(value):
        value = str(value or "").strip()
        if not value or value in {".", ".."} or "/" in value or "\\" in value:
            raise ValueError("Nombre de carpeta invalido.")
        return value

    def categories(self):
        return list(self.ROOT_CATEGORIES)

    def folder(self, category, levels=()):
        parts = [self._safe_part(category)]
        parts.extend(self._safe_part(x) for x in levels if str(x or "").strip())
        path = self.library_root.joinpath(*parts).resolve()
        path.relative_to(self.library_root)
        return path

    def children(self, category, levels=()):
        parent = self.folder(category, levels)
        if not parent.exists():
            return []
        try:
            return sorted([p.name for p in parent.iterdir() if p.is_dir()], key=str.casefold)
        except OSError:
            return []

    def ensure_path(self, category, levels=()):
        path = self.folder(category, levels)
        path.mkdir(parents=True, exist_ok=True)
        return path
