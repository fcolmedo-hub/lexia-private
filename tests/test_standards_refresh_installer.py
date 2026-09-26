import importlib.util
from pathlib import Path
import subprocess

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "install_standards_refresh.py"


@pytest.fixture
def installer():
    spec = importlib.util.spec_from_file_location("standards_refresh_installer_test", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def checkout(tmp_path, monkeypatch, installer):
    destination = tmp_path / "checkout"
    # Local development has an equivalent commit tree with a different SHA
    # from the connector-published parent. CI uses the published parent.
    base = installer.BASE
    if subprocess.run(["git", "cat-file", "-e", f"{base}^{{commit}}"], cwd=ROOT, capture_output=True).returncode:
        first_install = subprocess.check_output([
            "git", "log", "--diff-filter=A", "-1", "--format=%H", "--", "services/standards_pipeline.py"
        ], cwd=ROOT).decode().strip()
        base = subprocess.check_output(["git", "rev-parse", f"{first_install}^"], cwd=ROOT).decode().strip()
        monkeypatch.setattr(installer, "BASE", base)
    subprocess.run(["git", "clone", "--shared", "--no-checkout", str(ROOT), str(destination)], check=True, capture_output=True)
    subprocess.run(["git", "checkout", base], cwd=destination, check=True, capture_output=True)
    reviewed = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT).decode().strip()
    subprocess.run(["git", "fetch", "origin", reviewed], cwd=destination, check=True, capture_output=True)
    home = tmp_path / "home"
    (home / "Desktop").mkdir(parents=True)
    monkeypatch.setattr(Path, "home", lambda: home)
    monkeypatch.chdir(destination)
    return destination, home


def test_preflight_backup_and_repeat(installer, checkout):
    destination, home = checkout
    installer.main(["--check"])
    assert not (destination / "services/standards_pipeline.py").exists()
    installer.main([])
    assert installer.installed(destination)
    assert len(list((home / "Desktop").glob("*/archivos-anteriores.tar.gz"))) == 1
    installer.main([])
    assert len(list((home / "Desktop").iterdir())) == 1


def test_local_conflict_blocks_every_file(installer, checkout):
    destination, home = checkout
    changed = destination / "app/ui2/assets/standards_nav_fix.js"
    changed.write_text("local work\n", encoding="utf-8")
    before = changed.read_bytes()
    with pytest.raises(SystemExit, match="no se modificó ningún archivo"):
        installer.main([])
    assert changed.read_bytes() == before
    assert not (destination / "services/standards_pipeline.py").exists()
    assert list((home / "Desktop").iterdir()) == []


def test_upgrade_from_previously_installed_standards_refresh(installer, checkout, monkeypatch):
    destination, home = checkout
    latest = subprocess.check_output(["git", "rev-parse", "FETCH_HEAD"], cwd=destination).decode().strip()
    first = subprocess.check_output([
        "git", "log", "--diff-filter=A", "-1", "--format=%H", "--", "services/standards_pipeline.py"
    ], cwd=ROOT).decode().strip()
    monkeypatch.setattr(installer, "PREVIOUS", (first,))
    subprocess.run(["git", "fetch", "origin", first], cwd=destination, check=True, capture_output=True)
    installer.main([])
    subprocess.run(["git", "fetch", "origin", latest], cwd=destination, check=True, capture_output=True)
    installer.main(["--check"])
    installer.main([])
    assert installer.installed(destination)
    assert len(list((home / "Desktop").glob("*/archivos-anteriores.tar.gz"))) == 2
