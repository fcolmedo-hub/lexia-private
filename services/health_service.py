import os
import platform
import shutil
import sqlite3
from pathlib import Path

from config.settings import SETTINGS
from version import __version__


class HealthService:

    def run(self) -> dict:
        """
        Compatibilidad con versiones anteriores.
        """
        return self.report()

    def report(self) -> dict:
        runtime_usage = shutil.disk_usage(
            SETTINGS.runtime_path.resolve().anchor
            or os.getcwd()
        )

        checks = {
            "version": __version__,
            "python": platform.python_version(),
            "platform": platform.platform(),
            "library_exists": SETTINGS.library_path.exists(),
            "catalog_exists": SETTINGS.catalog_path.exists(),
            "qdrant_exists": SETTINGS.vector_path.exists(),
            "runtime_writable": self._writable(SETTINGS.runtime_path),
            "free_disk_gb": round(runtime_usage.free / (1024 ** 3), 2),
            "catalog_integrity": self._sqlite_integrity(
                SETTINGS.catalog_path
            ),
            "cases_integrity": self._sqlite_integrity(
                SETTINGS.cases_path
            ),
        }

        checks["healthy"] = all(
            [
                checks["library_exists"],
                checks["runtime_writable"],
                checks["catalog_integrity"] in {"ok", "missing"},
                checks["cases_integrity"] in {"ok", "missing"},
                checks["free_disk_gb"] > 1,
            ]
        )

        return checks

    def _writable(self, path: Path) -> bool:
        try:
            path.mkdir(parents=True, exist_ok=True)
            probe = path / ".write_test"
            probe.write_text("ok", encoding="utf-8")
            probe.unlink(missing_ok=True)
            return True
        except Exception:
            return False

    def _sqlite_integrity(self, path: Path) -> str:
        if not path.exists():
            return "missing"

        try:
            with sqlite3.connect(path) as connection:
                row = connection.execute(
                    "PRAGMA integrity_check"
                ).fetchone()
            return str(row[0]) if row else "unknown"
        except Exception as error:
            return f"error: {error}"
