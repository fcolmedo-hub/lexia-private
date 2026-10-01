import platform
import sys

import cv2
import numpy as np
import pytest
from rapidocr_onnxruntime.ch_ppocr_det import utils

from core import ocr_worker
from scripts import install_macos_ocr_resize as installer


@pytest.mark.parametrize("system,machine", [("win32", "AMD64"), ("linux", "aarch64"), ("darwin", "x86_64")])
def test_other_platforms_leave_opencv_intact(monkeypatch, system, machine):
    original = utils.cv2
    monkeypatch.setattr(sys, "platform", system)
    monkeypatch.setattr(platform, "machine", lambda: machine)
    assert not ocr_worker._configure_macos_detector_resize()
    assert utils.cv2 is original


def test_real_detector_uses_area_and_keeps_other_opencv_calls(monkeypatch):
    monkeypatch.setattr(utils, "cv2", cv2)
    monkeypatch.setattr(sys, "platform", "darwin")
    monkeypatch.setattr(platform, "machine", lambda: "arm64")
    assert ocr_worker._configure_macos_detector_resize()
    proxy = utils.cv2
    assert ocr_worker._configure_macos_detector_resize()
    assert utils.cv2 is proxy
    assert utils.cv2.findContours is cv2.findContours
    assert proxy.resize.__self__ is proxy
    image = np.random.default_rng(7).integers(0, 256, (1991, 1412, 3), dtype=np.uint8)
    actual = utils.DetPreProcess().resize(image)
    expected = cv2.resize(image, (1408, 1984), interpolation=cv2.INTER_AREA)
    assert np.array_equal(actual, expected)


def original_worker():
    return "import sys\n\ndef _lines(result) -> list[str]:\n    return result\n\ndef main():\n    engine = RapidOCR()\n    return engine\n"


def test_worker_configures_detector_before_creating_engine(monkeypatch, tmp_path):
    monkeypatch.setattr(utils, "cv2", cv2)
    monkeypatch.setattr(sys, "platform", "darwin")
    monkeypatch.setattr(platform, "machine", lambda: "arm64")
    monkeypatch.setattr(sys, "argv", ["worker", "fixture.pdf", "[]", "170", str(tmp_path / "result.jsonl")])

    def create_engine():
        assert isinstance(utils.cv2, ocr_worker._MacOCRDetectorCV2)
        return object()

    class Document:
        def close(self):
            pass

    monkeypatch.setattr(ocr_worker, "RapidOCR", create_engine)
    monkeypatch.setattr(ocr_worker.fitz, "open", lambda _path: Document())
    assert ocr_worker.main() == 0


@pytest.mark.parametrize("bom,newline", [(False, "\n"), (True, "\r\n")])
def test_installer_preserves_local_edits_format_and_backup(tmp_path, bom, newline):
    path = tmp_path / installer.TARGET
    path.parent.mkdir()
    original = (("\ufeff" if bom else "") + (original_worker() + "\n# Local OCR customization\n").replace("\n", newline)).encode()
    path.write_bytes(original)
    path.chmod(0o640)
    installer.install(tmp_path, check=True)
    assert path.read_bytes() == original
    assert len(list(path.parent.iterdir())) == 1
    backup = installer.install(tmp_path)
    assert backup.read_bytes() == original
    updated = path.read_bytes()
    assert updated.startswith(b"\xef\xbb\xbf") == bom
    assert (b"\r\n" in updated) == (newline == "\r\n")
    assert "# Local OCR customization" in updated.decode("utf-8-sig")
    assert path.stat().st_mode & 0o777 == 0o640
    assert installer.install(tmp_path) is None
    assert path.read_bytes() == updated
    assert len(list(path.parent.iterdir())) == 2


@pytest.mark.parametrize("text", ["invalid python !", "def other_worker():\n    pass\n", "def _configure_macos_detector_resize():\n    pass\n"])
def test_installer_rejects_unknown_worker_without_writing(tmp_path, text):
    path = tmp_path / installer.TARGET
    path.parent.mkdir()
    path.write_text(text)
    with pytest.raises((ValueError, SyntaxError)):
        installer.install(tmp_path)
    assert path.read_text() == text
    assert len(list(path.parent.iterdir())) == 1


def test_installer_rejects_symlink(tmp_path):
    target = tmp_path / "original.py"
    target.write_text(original_worker())
    path = tmp_path / installer.TARGET
    path.parent.mkdir()
    path.symlink_to(target)
    with pytest.raises(ValueError):
        installer.install(tmp_path)
    assert target.read_text() == original_worker()
