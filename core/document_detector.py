import os
from pathlib import Path
from typing import Callable, Iterable

from models.document import Document


class DocumentDetector:
    SUPPORTED_EXTENSIONS = {".pdf", ".doc", ".docx", ".odt", ".txt", ".html", ".htm"}

    def __init__(self, library_path: str | Path):
        self.library_path = Path(library_path).resolve()
        self.library_path.mkdir(parents=True, exist_ok=True)

    def scan(
        self,
        paths: Iterable[str | Path] | None = None,
        progress_callback: (
            Callable[[int, int, str], None] | None
        ) = None,
    ) -> list[Document]:
        if paths is None:
            file_paths = list(self._walk_fast(self.library_path))
        else:
            file_paths = self._normalize_paths(paths)

        total = len(file_paths)
        documents: list[Document] = []

        for position, file_path in enumerate(file_paths, start=1):
            if progress_callback:
                progress_callback(
                    position - 1,
                    total,
                    str(file_path),
                )

            try:
                stat = file_path.stat()
            except OSError:
                continue

            documents.append(
                Document(
                    name=file_path.name,
                    path=file_path,
                    category=self._infer_category(file_path),
                    extension=file_path.suffix.lower(),
                    size=stat.st_size,
                    modified_ns=stat.st_mtime_ns,
                    physical_folder=self._physical_folder(
                        file_path
                    ),
                )
            )

            if progress_callback:
                progress_callback(
                    position,
                    total,
                    str(file_path),
                )

        return documents

    def all_active_paths(self) -> set[str]:
        return {
            str(path.resolve())
            for path in self._walk_fast(self.library_path)
        }

    def _walk_fast(self, root: Path):
        if not root.exists():
            return

        stack = [root]

        while stack:
            directory = stack.pop()

            try:
                with os.scandir(directory) as entries:
                    for entry in entries:
                        try:
                            if entry.is_dir(
                                follow_symlinks=False
                            ):
                                stack.append(Path(entry.path))
                                continue

                            if not entry.is_file(
                                follow_symlinks=False
                            ):
                                continue
                        except OSError:
                            continue

                        path = Path(entry.path)

                        if (
                            path.suffix.lower()
                            in self.SUPPORTED_EXTENSIONS
                        ):
                            yield path.resolve()

            except (OSError, PermissionError):
                continue

    def _normalize_paths(
        self,
        paths: Iterable[str | Path],
    ) -> list[Path]:
        found: dict[str, Path] = {}

        for raw in paths:
            path = Path(raw).resolve()

            if path.is_dir():
                candidates = self._walk_fast(path)
            else:
                candidates = (path,)

            for candidate in candidates:
                if (
                    candidate.exists()
                    and candidate.is_file()
                    and candidate.suffix.lower()
                    in self.SUPPORTED_EXTENSIONS
                ):
                    found[str(candidate)] = candidate

        return sorted(
            found.values(),
            key=lambda item: str(item).lower(),
        )

    def _infer_category(self, path: Path) -> str:
        """Infere la categoría desde la primera carpeta relativa."""
        try:
            relative = path.relative_to(self.library_path)
        except ValueError:
            return "Sin clasificar"

        if len(relative.parts) <= 1:
            return "Sin clasificar"

        category = relative.parts[0].strip()
        return category or "Sin clasificar"

    def _physical_folder(self, path: Path) -> str:
        try:
            relative = path.relative_to(
                self.library_path
            )
        except ValueError:
            return ""

        return (
            str(relative.parent)
            if str(relative.parent) != "."
            else ""
        )
