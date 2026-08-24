import importlib.util
import json
import sys
from pathlib import Path


ROOT = Path(__file__).parents[1]


def _load_settings(monkeypatch, tmp_path):
    data_root = tmp_path / "LexIA Data"
    library_root = tmp_path / "Biblioteca nueva"
    monkeypatch.setattr(sys, "platform", "darwin")
    monkeypatch.setenv("LEXIA_DATA_ROOT", str(data_root))
    monkeypatch.setenv("LEXIA_LIBRARY_PATH", str(library_root))

    spec = importlib.util.spec_from_file_location(
        "lexia_macos_settings_test",
        ROOT / "config" / "settings.py",
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module.Settings(), data_root, library_root


def test_macos_uses_an_empty_library_outside_the_repository(
    monkeypatch,
    tmp_path,
):
    settings, data_root, library_root = _load_settings(monkeypatch, tmp_path)

    assert settings.library_path == library_root
    assert settings.runtime_path == data_root / "runtime"
    assert settings.catalog_path == data_root / "runtime" / "lexia_catalog.sqlite3"
    assert settings.vector_path == data_root / "runtime" / "qdrant_local"
    assert settings.qdrant_mode == "local"
    assert ROOT not in settings.library_path.parents


def test_release_accepts_local_or_server_qdrant():
    manifest = json.loads((ROOT / "RELEASE.json").read_text(encoding="utf-8"))

    assert manifest["qdrant_mode"] == "server"
    assert set(manifest["qdrant_modes"]) == {"server", "local"}


def test_macos_installer_and_launcher_keep_data_outside_the_repo():
    installer = (
        ROOT / "scripts" / "install_macos_3_4.sh"
    ).read_text(encoding="utf-8")
    launcher = (
        ROOT / "INICIAR_LEXIA_MAC.command"
    ).read_text(encoding="utf-8")
    classic_launcher = (ROOT / "run_lexia.py").read_text(encoding="utf-8")

    assert 'LIBRARY_ROOT="$HOME/Documents/LexIA Biblioteca"' in installer
    assert 'DATA_ROOT="$HOME/Library/Application Support/LexIA"' in installer
    assert '"qdrant_mode": "local"' in installer
    assert 'export LEXIA_CLASSIC_HEADLESS=1' in launcher
    assert '"$PYTHON_BIN" "$ROOT/run_lexia.py"' in launcher
    assert '"$PYTHON_BIN" "$ROOT/app/ui2/launch_ui2.py"' in launcher
    assert 'LEXIA_CLASSIC_HEADLESS' in classic_launcher
