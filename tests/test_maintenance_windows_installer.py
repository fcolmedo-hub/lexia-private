"""Installer rehearsal on a temporary checkout, never on a real library."""
import importlib.util
from pathlib import Path
import subprocess

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "install_maintenance_windows.py"


@pytest.fixture(scope="module")
def installer():
    spec = importlib.util.spec_from_file_location("maintenance_windows_installer_test", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def temporary_checkout(tmp_path, monkeypatch, installer):
    checkout = tmp_path / "checkout"
    subprocess.run(["git", "clone", "--shared", "--no-checkout", str(ROOT), str(checkout)], check=True, capture_output=True)
    subprocess.run(["git", "checkout", "400a1013e493438d6c898a9a55bb6861e97fd691"], cwd=checkout, check=True, capture_output=True)
    # FETCH_HEAD is the reviewed remote commit, not the in-progress local test commit.
    reviewed = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT).decode().strip()
    subprocess.run(["git", "fetch", "origin", reviewed], cwd=checkout, check=True, capture_output=True)
    backup_home = tmp_path / "test-home"
    (backup_home / "Desktop").mkdir(parents=True)
    monkeypatch.setattr(Path, "home", lambda: backup_home)
    monkeypatch.chdir(checkout)
    return checkout, backup_home


def test_all_phases_are_checked_backed_up_and_repeatable(installer, temporary_checkout, capsys):
    checkout, backup_home = temporary_checkout
    baseline = (checkout / "app/ui2/assets/windows_maintenance_duplicates.js").read_bytes()
    installer.main(["--check"])
    assert (checkout / "app/ui2/assets/windows_maintenance_duplicates.js").read_bytes() == baseline
    assert list((backup_home / "Desktop").iterdir()) == []

    installer.main([])
    assert installer.phase_installed(checkout, 3)
    assert len(list((backup_home / "Desktop").glob("*/archivos-anteriores.tar.gz"))) == 1
    installer.main([])
    assert len(list((backup_home / "Desktop").iterdir())) == 1
    assert "ya instalada" in capsys.readouterr().out


def test_prior_update_and_conflict_never_overwrite_local_work(installer, temporary_checkout, capsys):
    checkout, backup_home = temporary_checkout
    # Imitate someone who already applied the OCR and AutoSync phases.
    for _, before, after, names in installer.PHASES[:2]:
        patch = installer.git("diff", before, after, "--", *names, cwd=checkout).stdout
        assert installer.git("apply", "-", cwd=checkout, data=patch).returncode == 0
    installer.main([])
    output = capsys.readouterr().out
    assert "ya instalada" in output and "pendiente" in output
    assert installer.phase_installed(checkout, 3)

    # A later local edit must block a repeat only if it overlaps the patch.
    altered = checkout / "app/ui2/assets/windows_maintenance_duplicates.js"
    original = installer.git(
        "show", "400a1013e493438d6c898a9a55bb6861e97fd691:app/ui2/assets/windows_maintenance_duplicates.js",
        cwd=checkout,
    )
    assert original.returncode == 0
    altered.write_bytes(original.stdout)
    altered.write_text("local change that must survive\n", encoding="utf-8")
    before = altered.read_bytes()
    with pytest.raises(SystemExit, match="No se modificó tu instalación"):
        installer.main([])
    assert altered.read_bytes() == before
    assert len(list((backup_home / "Desktop").iterdir())) == 1
