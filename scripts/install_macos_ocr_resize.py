#!/usr/bin/env python3
"""Instala el redimensionado OCR seguro en Mac con Apple Silicon, con respaldo."""
from __future__ import annotations

import argparse
import ast
from datetime import datetime
import os
from pathlib import Path
import platform
import shutil
import stat
import sys
import tempfile

TARGET = Path("core/ocr_worker.py")
HELPER = '''class _MacOCRDetectorCV2:
    """Keep OpenCV operations, using a safe detector resize on Apple Silicon."""

    def __init__(self, cv2_module):
        self._cv2 = cv2_module

    def __getattr__(self, name):
        return getattr(self._cv2, name)

    def resize(self, image, dimensions):
        # OpenCV 5.0 INTER_LINEAR can SIGSEGV when rounding RGB page sizes
        # down to multiples of 32 on arm64 macOS (opencv/opencv#29794).
        # This proxy belongs only to RapidOCR's detector utilities; the global
        # cv2 module and recognition/classification preprocessing stay intact.
        return self._cv2.resize(
            image, dimensions, interpolation=self._cv2.INTER_AREA
        )


def _configure_macos_detector_resize() -> bool:
    import platform

    if sys.platform != "darwin" or platform.machine().lower() != "arm64":
        return False
    from rapidocr_onnxruntime.ch_ppocr_det import utils

    if not isinstance(utils.cv2, _MacOCRDetectorCV2):
        utils.cv2 = _MacOCRDetectorCV2(utils.cv2)
    return True


'''
OLD_ENGINE = "    engine = RapidOCR()\n"
NEW_ENGINE = "    _configure_macos_detector_resize()\n" + OLD_ENGINE
ANCHOR = "def _lines(result) -> list[str]:\n"


def patched_worker(text: str) -> str:
    ast.parse(text)
    if HELPER in text and text.count(NEW_ENGINE) == 1:
        return text
    if "_configure_macos_detector_resize" in text or "_MacOCRDetectorCV2" in text:
        raise ValueError("Existe una corrección OCR diferente; se conservó el archivo.")
    if text.count(ANCHOR) != 1 or text.count(OLD_ENGINE) != 1:
        raise ValueError("El trabajador OCR tiene una estructura diferente; se conservó el archivo.")
    updated = text.replace(ANCHOR, HELPER + ANCHOR, 1)
    updated = updated.replace(OLD_ENGINE, NEW_ENGINE, 1)
    ast.parse(updated)
    return updated


def install(root: Path, *, check: bool = False) -> Path | None:
    path = root / TARGET
    if not path.is_file() or path.is_symlink():
        raise ValueError(f"No se encontró un archivo regular: {path}")
    original = path.read_bytes()
    decoded = original.decode("utf-8-sig")
    normalized = decoded.replace("\r\n", "\n")
    updated = patched_worker(normalized)
    if updated == normalized:
        print("La corrección OCR ya está instalada. No se modificó LexIA.")
        return None
    if check:
        print("Comprobación correcta. Se actualizará solamente core/ocr_worker.py.")
        return None
    newline = "\r\n" if decoded.count("\r\n") > decoded.count("\n") / 2 else "\n"
    bom = "\ufeff" if original.startswith(b"\xef\xbb\xbf") else ""
    data = (bom + updated.replace("\n", newline)).encode("utf-8")
    backup = path.with_name(path.name + ".respaldo-ocr-" + datetime.now().strftime("%Y%m%d-%H%M%S-%f"))
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, prefix="lexia-ocr-", suffix=".tmp", delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(data)
        os.chmod(temporary, stat.S_IMODE(path.stat().st_mode))
        if path.read_bytes() != original:
            raise ValueError("El archivo cambió durante la instalación; se conservó el archivo.")
        shutil.copy2(path, backup)
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    print(f"Corrección OCR instalada. Respaldo: {backup}")
    return backup


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Comprobar sin escribir")
    args = parser.parse_args()
    try:
        if sys.platform != "darwin" or platform.machine().lower() != "arm64":
            raise ValueError("Este instalador corresponde a Mac con Apple Silicon.")
        install(Path.cwd(), check=args.check)
        return 0
    except (OSError, ValueError, UnicodeError, SyntaxError) as exc:
        print(f"No se instaló la corrección OCR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
