import json
from pathlib import Path

from services.release_manifest_service import ReleaseManifestService


def test_release_manifest_exists():
    data = json.loads(Path("RELEASE.json").read_text(encoding="utf-8"))
    assert data["platform_version"]
    assert data["schema_version"] >= 1
    assert data["qdrant_mode"] == "server"


def test_run_lexia_has_release_guard():
    source = Path("run_lexia.py").read_text(encoding="utf-8")
    assert "ReleaseManifestService" in source
    assert ".startup_guard()" in source
