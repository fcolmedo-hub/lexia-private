from __future__ import annotations

import json
import platform
import sqlite3
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from config.settings import SETTINGS


class ReleaseManifestError(RuntimeError):
    pass


class ReleaseManifestService:
    """
    Guard liviano de release.

    No modifica esquemas de negocio durante el arranque.
    Registra una baseline de la plataforma y bloquea arranques incompatibles.
    """

    BASELINE_SCHEMA_VERSION = 1
    BASELINE_MIGRATION = "baseline_platform_2_3"

    def __init__(self, root: str | Path | None = None):
        self.root = Path(root or Path.cwd()).resolve()
        self.manifest_path = self.root / "RELEASE.json"
        self.runtime_path = Path(SETTINGS.runtime_path)
        if not self.runtime_path.is_absolute():
            self.runtime_path = (self.root / self.runtime_path).resolve()

        self.state_path = self.runtime_path / "release_state.json"
        self.migrations_db = self.runtime_path / "schema_migrations.sqlite3"

    def startup_guard(self) -> dict[str, Any]:
        manifest = self.load_manifest()
        self._validate_python(manifest)
        self._validate_qdrant_contract(manifest)

        self.runtime_path.mkdir(parents=True, exist_ok=True)
        self._ensure_migrations_db()

        state = self._load_state()
        expected = int(manifest.get("schema_version", self.BASELINE_SCHEMA_VERSION))

        if state is None:
            self._bootstrap_baseline(expected)
            state = self._load_state() or {}

        current = int(state.get("schema_version", 0))

        if current > expected:
            raise ReleaseManifestError(
                "La base runtime pertenece a un esquema más nuevo "
                f"({current}) que esta release ({expected}). "
                "No se inicia LexIA para evitar corrupción."
            )

        if current < expected:
            raise ReleaseManifestError(
                "La instalación requiere una migración de esquema "
                f"{current} -> {expected}. Ejecutá: "
                r".\.venv\Scripts\python.exe tools\lexia_migrate.py"
            )

        return {
            "platform_version": manifest.get("platform_version"),
            "schema_version": current,
            "qdrant_collection": manifest.get("qdrant_collection"),
            "python": manifest.get("python_runtime"),
        }

    def load_manifest(self) -> dict[str, Any]:
        if not self.manifest_path.exists():
            raise ReleaseManifestError(
                f"No existe {self.manifest_path.name}. "
                "La instalación de LexIA no tiene manifiesto de release."
            )

        try:
            data = json.loads(self.manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise ReleaseManifestError(
                f"No se pudo leer RELEASE.json: {error}"
            ) from error

        required = {
            "platform_version",
            "schema_version",
            "python_runtime",
            "qdrant_mode",
            "qdrant_collection",
        }
        missing = sorted(required - set(data))
        if missing:
            raise ReleaseManifestError(
                "RELEASE.json incompleto. Faltan: " + ", ".join(missing)
            )
        return data

    def _validate_python(self, manifest: dict[str, Any]) -> None:
        expected = str(manifest.get("python_runtime", "")).strip()
        current = f"{sys.version_info.major}.{sys.version_info.minor}"
        if expected and current != expected:
            raise ReleaseManifestError(
                f"Python incompatible. Release={expected}; actual={current}. "
                "Usá el entorno Python fijado para esta release."
            )

    def _validate_qdrant_contract(self, manifest: dict[str, Any]) -> None:
        expected_mode = str(manifest.get("qdrant_mode", "")).strip()
        actual_mode = str(getattr(SETTINGS, "qdrant_mode", "")).strip()

        if expected_mode and actual_mode != expected_mode:
            raise ReleaseManifestError(
                "Contrato Qdrant incompatible: "
                f"RELEASE={expected_mode}, SETTINGS={actual_mode}."
            )

        expected_collection = str(
            manifest.get("qdrant_collection", "")
        ).strip()
        actual_collection = str(
            getattr(SETTINGS, "collection_name", "")
        ).strip()

        if expected_collection and actual_collection != expected_collection:
            raise ReleaseManifestError(
                "Colección Qdrant incompatible: "
                f"RELEASE={expected_collection}, "
                f"SETTINGS={actual_collection}."
            )

    def _ensure_migrations_db(self) -> None:
        with sqlite3.connect(self.migrations_db) as con:
            con.execute(
                """
                CREATE TABLE IF NOT EXISTS schema_migrations (
                    version INTEGER PRIMARY KEY,
                    migration_id TEXT NOT NULL UNIQUE,
                    applied_at TEXT NOT NULL,
                    platform_version TEXT NOT NULL,
                    notes TEXT NOT NULL DEFAULT ''
                )
                """
            )
            con.commit()

    def _load_state(self) -> dict[str, Any] | None:
        if not self.state_path.exists():
            return None
        try:
            return json.loads(self.state_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise ReleaseManifestError(
                f"No se pudo leer {self.state_path.name}: {error}"
            ) from error

    def _bootstrap_baseline(self, version: int) -> None:
        manifest = self.load_manifest()
        now = datetime.now().isoformat(timespec="seconds")

        state = {
            "schema_version": version,
            "platform_version": manifest["platform_version"],
            "baseline": True,
            "created_at": now,
        }
        self.state_path.write_text(
            json.dumps(state, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        with sqlite3.connect(self.migrations_db) as con:
            con.execute(
                """
                INSERT OR IGNORE INTO schema_migrations (
                    version, migration_id, applied_at,
                    platform_version, notes
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    version,
                    self.BASELINE_MIGRATION,
                    now,
                    manifest["platform_version"],
                    "Baseline del estado estable existente al instalar "
                    "Release Manifest + Migration Guard 1.0.",
                ),
            )
            con.commit()

    def migration_status(self) -> dict[str, Any]:
        manifest = self.load_manifest()
        state = self._load_state()
        return {
            "release_schema": int(manifest["schema_version"]),
            "runtime_schema": (
                int(state["schema_version"])
                if state is not None
                else None
            ),
            "state_path": str(self.state_path),
            "migrations_db": str(self.migrations_db),
        }
