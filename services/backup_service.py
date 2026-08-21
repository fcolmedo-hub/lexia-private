import json
import shutil
import sqlite3
from datetime import datetime
from pathlib import Path

from config.settings import SETTINGS
from version import __version__


class BackupService:
    DATABASES = (
        SETTINGS.catalog_path,
        SETTINGS.cases_path,
        SETTINGS.feedback_path,
        SETTINGS.jobs_path,
    )

    def create(self) -> Path:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        destination = SETTINGS.backups_path / f"lexia_{timestamp}"
        destination.mkdir(parents=True, exist_ok=False)

        copied = []

        for database in self._databases_to_copy():
            if not database.exists():
                continue

            target = destination / database.name
            self._sqlite_backup(database, target)
            copied.append(database.name)

        copied_config = []
        for config in self._configuration_files():
            if not config.exists():
                continue
            shutil.copy2(config, destination / config.name)
            copied_config.append(config.name)

        manifest = {
            "version": __version__,
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "files": copied + copied_config,
            "knowledge_included": (
                Path(SETTINGS.knowledge_path).name in copied
            ),
            "qdrant_included": False,
            "note": (
                "Incluye las bases SQLite de runtime, incluida Knowledge, "
                "y la configuración operativa. El índice Qdrant y la "
                "biblioteca física no se copian en la copia operativa."
            ),
        }

        (destination / "manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        self._rotate()
        return destination

    def _databases_to_copy(self) -> list[Path]:
        """Include every runtime SQLite database, not only the legacy four.

        Knowledge, OCR state and other operational stores are part of a
        recoverable LexIA state. SQLite's online backup API keeps each copy
        consistent even while the application is open.
        """
        candidates = list(self.DATABASES)
        runtime = Path(SETTINGS.runtime_path)
        if runtime.exists():
            candidates.extend(runtime.glob("*.sqlite3"))
        candidates.extend(
            [
                Path(SETTINGS.knowledge_path),
                Path(SETTINGS.ocr_queue_path),
                Path(SETTINGS.search_cache_path),
                Path(SETTINGS.matrix_path),
                Path(SETTINGS.query_interpretations_path),
                Path(SETTINGS.precedent_path),
                Path(SETTINGS.strategy_path),
                Path(SETTINGS.drafting_path),
            ]
        )
        unique = {}
        for candidate in candidates:
            resolved = candidate.resolve()
            unique[str(resolved).lower()] = resolved
        return sorted(unique.values(), key=lambda path: path.name.lower())

    def _configuration_files(self) -> list[Path]:
        return [
            Path(SETTINGS.app_state_path),
            Path(SETTINGS.autosync_state_path),
            Path(SETTINGS.reconciliation_config_path),
        ]

    def list_backups(self) -> list[Path]:
        SETTINGS.backups_path.mkdir(parents=True, exist_ok=True)

        return sorted(
            [
                path
                for path in SETTINGS.backups_path.iterdir()
                if path.is_dir() and path.name.startswith("lexia_")
            ],
            reverse=True,
        )

    def restore(self, backup_path: str | Path) -> None:
        source = Path(backup_path)

        if not source.exists():
            raise FileNotFoundError(source)

        for database in self.DATABASES:
            candidate = source / database.name

            if candidate.exists():
                database.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(candidate, database)

    def _sqlite_backup(
        self,
        source: Path,
        destination: Path,
    ) -> None:
        with sqlite3.connect(source) as source_connection:
            with sqlite3.connect(destination) as target_connection:
                source_connection.backup(target_connection)

    def _rotate(self) -> None:
        backups = self.list_backups()

        for old_backup in backups[SETTINGS.backup_retention:]:
            shutil.rmtree(old_backup, ignore_errors=True)
