"""Trabajador OCR aislado. Emite un resultado JSON por pagina."""

from __future__ import annotations

import io
import json
from pathlib import Path
import sys

import fitz
from PIL import Image, ImageOps
from rapidocr_onnxruntime import RapidOCR


def _lines(result) -> list[str]:
    return [] if not result else [
        str(item[1]).strip()
        for item in result
        if len(item) >= 2 and str(item[1]).strip()
    ]


def _render(page, dpi: int) -> Image.Image:
    pixmap = page.get_pixmap(
        matrix=fitz.Matrix(dpi / 72.0, dpi / 72.0),
        alpha=False,
    )
    with Image.open(io.BytesIO(pixmap.tobytes("png"))) as source:
        return source.convert("RGB")


def _recognize_page(engine, page, dpi: int) -> tuple[list[str], list[dict]]:
    """Run a normal pass and stronger fallbacks only when it finds no text."""
    attempts: list[dict] = []
    image = _render(page, dpi)
    result, _ = engine(image)
    lines = _lines(result)
    attempts.append({"mode": "normal", "dpi": dpi, "lines": len(lines)})
    if lines:
        return lines, attempts

    # Some perfectly visible PDFs render their glyphs as thin vector strokes.
    # At the standard queue resolution they can disappear for the detector even
    # though Preview displays them without difficulty.  Retry at a higher
    # resolution with contrast normalization before declaring the page empty.
    retry_dpi = max(260, dpi)
    enhanced = ImageOps.autocontrast(ImageOps.grayscale(_render(page, retry_dpi)))
    result, _ = engine(enhanced.convert("RGB"))
    lines = _lines(result)
    attempts.append({"mode": "contrast", "dpi": retry_dpi, "lines": len(lines)})
    if lines:
        return lines, attempts

    # A thresholded pass recovers faint scans and unusual embedded color maps.
    thresholded = enhanced.point(lambda value: 0 if value < 205 else 255)
    result, _ = engine(thresholded.convert("RGB"))
    lines = _lines(result)
    attempts.append({"mode": "threshold", "dpi": retry_dpi, "lines": len(lines)})
    return lines, attempts


def main() -> int:
    pdf_path = Path(sys.argv[1])
    pages = [int(value) for value in json.loads(sys.argv[2])]
    dpi = int(sys.argv[3])
    output_path = Path(sys.argv[4])
    engine = RapidOCR()
    document = fitz.open(pdf_path)
    try:
        for page_number in pages:
            page = document[page_number - 1]
            lines, attempts = _recognize_page(engine, page, dpi)
            with output_path.open("a", encoding="utf-8") as stream:
                stream.write(json.dumps(
                    {
                        "page": page_number,
                        "text": "\n".join(lines),
                        "attempts": attempts,
                    },
                    ensure_ascii=False,
                ) + "\n")
    finally:
        document.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
