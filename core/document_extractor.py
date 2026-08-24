from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path
import shutil
import subprocess
import tempfile
import zipfile
import xml.etree.ElementTree as ET
from typing import Callable

import fitz
from docx import Document as DocxDocument
from pypdf import PdfReader

from config.settings import SETTINGS
from core.ocr_service import OCRService
from services.libreoffice_locator import ensure_libreoffice_on_path


ensure_libreoffice_on_path()

class DocumentExtractionError(Exception):
    pass


@dataclass(slots=True)
class ExtractionResult:
    text: str
    method: str
    total_pages: int | None = None
    ocr_pages: int = 0
    needs_ocr: bool = False


class DocumentExtractor:
    def __init__(
        self,
        ocr_service: OCRService | None = None,
    ):
        self.ocr_service = ocr_service or OCRService()

    def extract(
        self,
        file_path: str | Path,
        allow_ocr: bool = False,
        progress_callback: (
            Callable[[int, int], None] | None
        ) = None,
    ) -> ExtractionResult:
        path = Path(file_path)
        extension = path.suffix.lower()

        if not path.exists():
            raise DocumentExtractionError(
                f"El archivo no existe: {path}"
            )

        try:
            if extension == ".pdf":
                self._validate_pdf_header(path)
                return self._extract_pdf(
                    path,
                    allow_ocr=allow_ocr,
                    progress_callback=progress_callback,
                )

            if extension == ".docx":
                return ExtractionResult(
                    text=self._extract_docx(path),
                    method="docx",
                )

            if extension == ".doc":
                with tempfile.TemporaryDirectory(prefix="lexia_doc_") as temporary:
                    output_path = Path(temporary) / f"{path.stem}.docx"
                    self._convert_doc_to_docx(path, output_path)
                    return ExtractionResult(
                        text=self._extract_docx(output_path),
                        method="doc_via_docx",
                    )

            if extension == ".odt":
                return ExtractionResult(
                    text=self._extract_odt(path),
                    method="odt",
                )

            if extension == ".txt":
                return ExtractionResult(
                    text=self._extract_txt(path),
                    method="txt",
                )

            if extension in {".html", ".htm"}:
                return ExtractionResult(
                    text=self._extract_html(path),
                    method="html",
                )

            raise DocumentExtractionError(
                f"Formato no soportado: "
                f"{extension or '[sin extensión]'}"
            )

        except DocumentExtractionError:
            raise
        except Exception as error:
            raise DocumentExtractionError(
                f"No se pudo procesar "
                f"'{path.name}': {error}"
            ) from error

    def _validate_pdf_header(
        self,
        path: Path,
    ) -> None:
        """Rechaza falsos PDF antes de pypdf, PyMuPDF u OCR."""
        try:
            with path.open("rb") as stream:
                header = stream.read(1024)
        except OSError as error:
            raise DocumentExtractionError(
                f"No se pudo leer el encabezado de "
                f"'{path.name}': {error}"
            ) from error

        if not header:
            raise DocumentExtractionError(
                f"PDF inválido: '{path.name}' está vacío."
            )

        if b"%PDF-" in header:
            return

        lowered = header.lower().lstrip()
        html_markers = (
            b"<!doctype html",
            b"<html",
            b"<head",
            b"<body",
            b"<?xml",
        )
        kind = (
            "contenido HTML o XML"
            if any(
                lowered.startswith(marker)
                for marker in html_markers
            )
            else "encabezado no reconocido"
        )

        raise DocumentExtractionError(
            f"PDF inválido: '{path.name}' no contiene "
            f"la firma %PDF-; se detectó {kind}. "
            f"Ruta: {path.resolve()}"
        )

    def _extract_pdf(
        self,
        path: Path,
        allow_ocr: bool,
        progress_callback=None,
    ) -> ExtractionResult:
        native_pages = self._extract_pdf_native(path)
        total_pages = len(native_pages)

        pages_requiring_ocr = self._pages_requiring_ocr(path, native_pages)

        if not pages_requiring_ocr:
            return ExtractionResult(
                text=self._join_pages(native_pages),
                method="native_pdf",
                total_pages=total_pages,
                needs_ocr=False,
            )

        if not allow_ocr:
            return ExtractionResult(
                text=self._join_pages(native_pages),
                method="ocr_pending",
                total_pages=total_pages,
                needs_ocr=True,
            )

        if total_pages > SETTINGS.ocr_max_pages_per_document:
            raise DocumentExtractionError(
                "El PDF supera el máximo de páginas "
                "configurado para OCR."
            )

        ocr_pages = self.ocr_service.extract_pdf_pages(
            path,
            pages_requiring_ocr,
            progress_callback=progress_callback,
            total_pages=total_pages,
        )

        merged_pages = dict(native_pages)

        for page_number, ocr_text in ocr_pages.items():
            if len(ocr_text.strip()) > len(
                merged_pages.get(page_number, "").strip()
            ):
                merged_pages[page_number] = ocr_text

        successful = sum(
            1
            for text in ocr_pages.values()
            if text.strip()
        )

        return ExtractionResult(
            text=self._join_pages(merged_pages),
            method=(
                "ocr_pdf"
                if len(pages_requiring_ocr) == total_pages
                else "hybrid_pdf"
            ),
            total_pages=total_pages,
            ocr_pages=successful,
            needs_ocr=False,
        )

    def _pages_requiring_ocr(
        self,
        path: Path | dict[int, str],
        pages: dict[int, str] | None = None,
    ) -> list[int]:
        # Compatibilidad con llamadas anteriores: _pages_requiring_ocr(pages)
        if pages is None:
            pages = path
            path = None

        if not pages:
            return []
        minimum = int(SETTINGS.ocr_min_chars_per_page)
        short_pages = [
            page_number
            for page_number, text in pages.items()
            if len((text or "").strip()) < minimum
        ]
        if not short_pages:
            return []
        # Una pagina sin texto y sin una imagen documental es una pagina en
        # blanco, no una pagina pendiente de OCR.
        image_pages = (
            short_pages
            if path is None
            else self._image_pages_with_content(path, short_pages)
        )
        if not image_pages:
            return []
        native_ratio = (len(pages) - len(image_pages)) / len(pages)
        if native_ratio >= 0.50:
            return []
        return image_pages

    def _image_pages_with_content(
        self,
        path: Path,
        candidates: list[int],
    ) -> list[int]:
        """Descarta hojas vacias y logos pequenos antes de solicitar OCR."""
        if not candidates:
            return []
        document = fitz.open(path)
        result: list[int] = []
        try:
            for page_number in candidates:
                page = document[page_number - 1]
                page_area = max(1.0, float(page.rect.width * page.rect.height))
                image_area = 0.0
                try:
                    for info in page.get_image_info(xrefs=True):
                        rect = fitz.Rect(info.get("bbox", (0, 0, 0, 0)))
                        image_area += max(0.0, float(rect.width * rect.height))
                except (AttributeError, TypeError, ValueError):
                    for image in page.get_images(full=True):
                        for rect in page.get_image_rects(image[0]):
                            image_area += max(0.0, float(rect.width * rect.height))

                # Sellos, firmas o logos pequenos no justifican OCR de pagina.
                if image_area / page_area < 0.10:
                    continue

                # Una pagina escaneada completamente blanca tambien se omite.
                pixmap = page.get_pixmap(
                    matrix=fitz.Matrix(0.5, 0.5),
                    colorspace=fitz.csGRAY,
                    alpha=False,
                )
                samples = pixmap.samples
                if not samples:
                    continue
                dark_pixels = sum(value < 245 for value in samples)
                if dark_pixels / len(samples) < 0.001:
                    continue
                result.append(page_number)
        finally:
            document.close()
        return result

    def _extract_pdf_native(
        self,
        path: Path,
    ) -> dict[int, str]:
        try:
            reader = PdfReader(path, strict=False)
            return {
                page_number: (
                    page.extract_text() or ""
                ).strip()
                for page_number, page in enumerate(
                    reader.pages,
                    start=1,
                )
            }
        except Exception:
            document = fitz.open(path)
            try:
                return {
                    page_number: (
                        document[page_number - 1]
                        .get_text("text")
                        .strip()
                    )
                    for page_number in range(
                        1,
                        len(document) + 1,
                    )
                }
            finally:
                document.close()

    def _join_pages(
        self,
        pages: dict[int, str],
    ) -> str:
        output = []
        for page_number in sorted(pages):
            text = pages[page_number].strip()
            if text:
                output.append(
                    f"--- PÁGINA {page_number} ---\n{text}"
                )
        return "\n\n".join(output).strip()

    def _convert_doc_to_docx(
        self,
        source_path: Path,
        output_path: Path,
    ) -> None:
        executable = shutil.which("soffice") or shutil.which("libreoffice")
        if not executable:
            raise DocumentExtractionError(
                "Para leer archivos .doc se requiere LibreOffice instalado."
            )
        output_path.parent.mkdir(parents=True, exist_ok=True)
        process = subprocess.run(
            [
                executable,
                "--headless",
                "--convert-to",
                "docx",
                "--outdir",
                str(output_path.parent),
                str(source_path),
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
            timeout=120,
        )
        generated = output_path.parent / f"{source_path.stem}.docx"
        if process.returncode != 0 or not generated.exists():
            detail = process.stderr.strip() or process.stdout.strip() or "conversión sin resultado"
            raise DocumentExtractionError(
                f"No se pudo convertir '{source_path.name}' a DOCX: {detail}"
            )
        if generated.resolve() != output_path.resolve():
            shutil.move(str(generated), str(output_path))

    def _extract_docx(self, path: Path) -> str:
        document = DocxDocument(path)
        return "\n\n".join(
            paragraph.text.strip()
            for paragraph in document.paragraphs
            if paragraph.text.strip()
        )

    def _extract_odt(self, path: Path) -> str:
        """Extrae texto de OpenDocument Text (.odt) sin LibreOffice."""
        try:
            with zipfile.ZipFile(path, "r") as archive:
                try:
                    content = archive.read("content.xml")
                except KeyError as error:
                    raise DocumentExtractionError(
                        f"ODT inválido: '{path.name}' no contiene content.xml."
                    ) from error
        except zipfile.BadZipFile as error:
            raise DocumentExtractionError(
                f"ODT inválido o corrupto: '{path.name}'."
            ) from error
        except OSError as error:
            raise DocumentExtractionError(
                f"No se pudo leer el ODT '{path.name}': {error}"
            ) from error

        try:
            root = ET.fromstring(content)
        except ET.ParseError as error:
            raise DocumentExtractionError(
                f"ODT inválido: content.xml de '{path.name}' no es XML válido."
            ) from error

        office_ns = "urn:oasis:names:tc:opendocument:xmlns:office:1.0"
        text_ns = "urn:oasis:names:tc:opendocument:xmlns:text:1.0"
        table_ns = "urn:oasis:names:tc:opendocument:xmlns:table:1.0"

        body = root.find(f"{{{office_ns}}}body")
        if body is None:
            return ""

        text_body = body.find(f"{{{office_ns}}}text")
        if text_body is None:
            return ""

        paragraph_tags = {
            f"{{{text_ns}}}p",
            f"{{{text_ns}}}h",
        }
        row_tag = f"{{{table_ns}}}table-row"
        cell_tag = f"{{{table_ns}}}table-cell"

        def node_text(node):
            return "".join(node.itertext()).strip()

        blocks = []
        table_paragraph_nodes = set()

        for row in text_body.iter(row_tag):
            for cell in row.findall(cell_tag):
                for node in cell.iter():
                    if node.tag in paragraph_tags:
                        table_paragraph_nodes.add(id(node))

        for node in text_body.iter():
            if node.tag in paragraph_tags and id(node) not in table_paragraph_nodes:
                value = node_text(node)
                if value:
                    blocks.append(value)

        for row in text_body.iter(row_tag):
            cells = []
            for cell in row.findall(cell_tag):
                value = node_text(cell)
                cells.append(value)
            if any(cells):
                blocks.append("\t".join(cells))

        return "\n\n".join(blocks).strip()

    def _extract_html(self, path: Path) -> str:
        """Extract readable local HTML while excluding scripts and styles."""
        class _TextCollector(HTMLParser):
            BLOCK_TAGS = {
                "address", "article", "br", "div", "footer", "h1", "h2",
                "h3", "h4", "h5", "h6", "header", "li", "main", "p",
                "section", "table", "td", "th", "tr",
            }

            def __init__(self):
                super().__init__(convert_charrefs=True)
                self.parts = []
                self.hidden_depth = 0

            def handle_starttag(self, tag, attrs):
                tag = tag.casefold()
                if tag in {"script", "style", "noscript", "template"}:
                    self.hidden_depth += 1
                elif tag in self.BLOCK_TAGS:
                    self.parts.append("\n")

            def handle_endtag(self, tag):
                tag = tag.casefold()
                if tag in {"script", "style", "noscript", "template"}:
                    self.hidden_depth = max(0, self.hidden_depth - 1)
                elif tag in self.BLOCK_TAGS:
                    self.parts.append("\n")

            def handle_data(self, data):
                if not self.hidden_depth and data.strip():
                    self.parts.append(data)

        raw = path.read_bytes()
        text = ""
        for encoding in ("utf-8-sig", "utf-8", "cp1252", "latin-1"):
            try:
                text = raw.decode(encoding)
                break
            except UnicodeDecodeError:
                continue
        if not text:
            raise DocumentExtractionError(
                f"No se pudo determinar la codificación de '{path.name}'."
            )

        parser = _TextCollector()
        try:
            parser.feed(text)
            parser.close()
        except Exception as error:
            raise DocumentExtractionError(
                f"HTML inválido: '{path.name}': {error}"
            ) from error

        lines = [
            " ".join(part.split())
            for part in "".join(parser.parts).splitlines()
            if part.strip()
        ]
        return "\n\n".join(lines).strip()

    def _extract_txt(self, path: Path) -> str:
        for encoding in (
            "utf-8",
            "utf-8-sig",
            "cp1252",
            "latin-1",
        ):
            try:
                return path.read_text(
                    encoding=encoding
                )
            except UnicodeDecodeError:
                continue
        raise DocumentExtractionError(
            f"No se pudo determinar la codificación "
            f"de '{path.name}'."
        )
