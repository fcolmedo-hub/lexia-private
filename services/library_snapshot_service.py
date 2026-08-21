import json
import os
from pathlib import Path


class LibrarySnapshotService:
    def __init__(
        self,
        library_path: str | Path,
        snapshot_path: str | Path,
        supported_extensions: set[str],
    ):
        self.library_path = Path(library_path)
        self.snapshot_path = Path(snapshot_path)
        self.supported_extensions = {
            str(value).lower()
            for value in supported_extensions
        }
        self.snapshot_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

    def initialized(self) -> bool:
        return self.snapshot_path.exists()

    def load(self) -> dict[str, list[int]]:
        if not self.snapshot_path.exists():
            return {}

        try:
            payload = json.loads(
                self.snapshot_path.read_text(
                    encoding="utf-8"
                )
            )
        except (OSError, ValueError, TypeError):
            return {}

        files = payload.get("files", {})
        if not isinstance(files, dict):
            return {}

        return {
            str(path): [
                int(values[0]),
                int(values[1]),
            ]
            for path, values in files.items()
            if isinstance(values, list)
            and len(values) >= 2
        }

    def scan(
        self,
    ) -> tuple[
        set[str],
        set[str],
        dict[str, list[int]],
    ]:
        previous = self.load()
        current: dict[str, list[int]] = {}

        if not self.library_path.exists():
            return set(), set(previous), current

        stack = [self.library_path]

        while stack:
            directory = stack.pop()

            try:
                with os.scandir(directory) as entries:
                    for entry in entries:
                        try:
                            if entry.is_dir(
                                follow_symlinks=False
                            ):
                                stack.append(
                                    Path(entry.path)
                                )
                                continue

                            if not entry.is_file(
                                follow_symlinks=False
                            ):
                                continue

                            suffix = Path(
                                entry.name
                            ).suffix.lower()

                            if suffix not in (
                                self.supported_extensions
                            ):
                                continue

                            stat = entry.stat(
                                follow_symlinks=False
                            )
                            resolved = str(
                                Path(entry.path).resolve()
                            )
                            current[resolved] = [
                                int(stat.st_size),
                                int(stat.st_mtime_ns),
                            ]
                        except OSError:
                            continue
            except OSError:
                continue

        changed = {
            path
            for path, signature in current.items()
            if previous.get(path) != signature
        }
        deleted = set(previous) - set(current)

        return changed, deleted, current

    def save(
        self,
        snapshot: dict[str, list[int]],
    ) -> None:
        temporary = self.snapshot_path.with_suffix(
            ".tmp"
        )
        temporary.write_text(
            json.dumps(
                {
                    "version": 1,
                    "files": snapshot,
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        temporary.replace(self.snapshot_path)

    def apply_changes(
        self,
        changed_paths: set[str],
        deleted_paths: set[str],
    ) -> None:
        snapshot = self.load()

        for path in deleted_paths:
            snapshot.pop(
                str(Path(path).resolve()),
                None,
            )

        for path in changed_paths:
            resolved = str(Path(path).resolve())
            file_path = Path(resolved)

            if (
                not file_path.exists()
                or file_path.suffix.lower()
                not in self.supported_extensions
            ):
                snapshot.pop(resolved, None)
                continue

            try:
                stat = file_path.stat()
            except OSError:
                continue

            snapshot[resolved] = [
                int(stat.st_size),
                int(stat.st_mtime_ns),
            ]

        self.save(snapshot)
