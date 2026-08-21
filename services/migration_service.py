import json
from pathlib import Path

from config.settings import SETTINGS
from version import __version__


class MigrationService:
    def __init__(
        self,
        marker_path: str | Path = "runtime/schema_version.json",
    ):
        self.marker_path = Path(marker_path)
        self.marker_path.parent.mkdir(parents=True, exist_ok=True)

    def migrate(self) -> dict:
        previous = self.current_version()

        payload = {
            "previous_version": previous,
            "current_version": __version__,
            "status": "ok",
        }

        self.marker_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        return payload

    def current_version(self) -> str | None:
        if not self.marker_path.exists():
            return None

        try:
            payload = json.loads(
                self.marker_path.read_text(encoding="utf-8")
            )
            return payload.get("current_version")
        except Exception:
            return None
