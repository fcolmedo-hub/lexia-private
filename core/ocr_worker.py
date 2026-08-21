"""Trabajador OCR aislado. Emite un resultado JSON por pagina."""

from __future__ import annotations

import io
import json
from pathlib import Path
import sys

import fitz
from PIL import Image
from rapidocr_onnxruntime import RapidOCR


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
            pixmap = page.get_pixmap(
                matrix=fitz.Matrix(dpi / 72.0, dpi / 72.0),
                alpha=False,
            )
            image = Image.open(io.BytesIO(pixmap.tobytes("png")))
            result, _ = engine(image)
            lines = [] if not result else [
                str(item[1]).strip()
                for item in result
                if len(item) >= 2 and str(item[1]).strip()
            ]
            with output_path.open("a", encoding="utf-8") as stream:
                stream.write(json.dumps(
                    {"page": page_number, "text": "\n".join(lines)},
                    ensure_ascii=False,
                ) + "\n")
    finally:
        document.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
