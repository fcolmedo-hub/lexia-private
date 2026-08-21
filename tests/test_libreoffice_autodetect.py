import os
from pathlib import Path

from services.libreoffice_locator import (
    ensure_libreoffice_on_path,
    locate_libreoffice,
)


def test_locator_candidate(
    tmp_path: Path,
    monkeypatch,
):
    monkeypatch.delenv(
        "LEXIA_LIBREOFFICE_PATH",
        raising=False,
    )
    monkeypatch.setattr(
        "services.libreoffice_locator.shutil.which",
        lambda command: None,
    )

    exe = tmp_path / (
        "soffice.exe"
        if os.name == "nt"
        else "soffice"
    )
    exe.write_bytes(b"x")

    status = locate_libreoffice([exe])

    assert status.found
    assert status.executable == str(
        exe.resolve()
    )


def test_ensure_process_path(
    tmp_path: Path,
    monkeypatch,
):
    exe = tmp_path / "soffice.exe"
    exe.write_bytes(b"x")

    monkeypatch.setenv(
        "LEXIA_LIBREOFFICE_PATH",
        str(exe),
    )
    monkeypatch.setenv(
        "PATH",
        str(tmp_path / "other"),
    )

    status = ensure_libreoffice_on_path()

    assert status.found
    assert str(tmp_path) in os.environ["PATH"]


def test_extractor_patch_present():
    source = Path(
        "core/document_extractor.py"
    ).read_text(
        encoding="utf-8"
    )

    assert (
        "ensure_libreoffice_on_path"
        in source
    )
