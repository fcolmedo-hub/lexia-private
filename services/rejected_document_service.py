from __future__ import annotations

import csv
import hashlib
import shutil
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import fitz

from config.settings import SETTINGS


@dataclass(frozen=True, slots=True)
class RejectedDocument:
    source_path: Path
    destination_path: Path
    category: str
    reason: str
    size: int
    sha256: str


class RejectedDocumentService:
    """Clasifica y aparta únicamente rechazos definitivos."""

    CATEGORIES = {
        "html_xml": "HTML o XML",
        "corrupt_pdf": "PDF corruptos",
        "encrypted_pdf": "PDF encriptados",
        "empty": "Vacíos",
        "read_error": "Error de lectura",
    }

    def __init__(self, root_path: str | Path | None = None):
        configured = getattr(SETTINGS, "rejected_documents_path", None)
        self.root_path = Path(
            root_path
            or configured
            or (SETTINGS.library_path.parent / "Rejected Documents")
        )
        self.log_path = self.root_path / "rejected_log.csv"

    def classify_definitive(self, path: str | Path) -> tuple[str, str] | None:
        file_path = Path(path)
        try:
            size = file_path.stat().st_size
        except OSError as error:
            return ("read_error", f"No se pudo leer el archivo: {error}")

        if size == 0:
            return ("empty", "El archivo está vacío.")
        if file_path.suffix.lower() != ".pdf":
            return None

        try:
            with file_path.open("rb") as stream:
                header = stream.read(4096)
        except OSError as error:
            return ("read_error", f"No se pudo leer el encabezado: {error}")

        lowered = header.lower().lstrip()
        html_markers = (b"<!doctype html", b"<html", b"<head", b"<body", b"<?xml")

        if b"%PDF-" not in header:
            if any(lowered.startswith(marker) for marker in html_markers):
                return ("html_xml", "Contenido HTML o XML guardado con extensión PDF.")
            return ("corrupt_pdf", "No contiene la firma PDF dentro de los primeros 4096 bytes.")

        try:
            document = fitz.open(file_path)
            try:
                if document.needs_pass:
                    return ("encrypted_pdf", "El PDF requiere contraseña.")
                if len(document) < 1:
                    return ("corrupt_pdf", "El PDF no contiene páginas.")
                document.load_page(0)
            finally:
                document.close()
        except Exception as error:
            return ("corrupt_pdf", f"PyMuPDF no pudo abrir el PDF: {error}")

        return None

    def quarantine(self, path: str | Path, category: str, reason: str) -> RejectedDocument:
        source = Path(path).resolve()
        folder_name = self.CATEGORIES.get(category, "Error de lectura")
        destination_dir = self.root_path / folder_name
        destination_dir.mkdir(parents=True, exist_ok=True)
        destination = self._unique_destination(destination_dir / source.name)
        size = source.stat().st_size
        digest = self._sha256(source)
        shutil.move(str(source), str(destination))
        result = RejectedDocument(source, destination, folder_name, reason, size, digest)
        self._append_log(result)
        return result

    def inspect_and_quarantine(self, path: str | Path) -> RejectedDocument | None:
        classification = self.classify_definitive(path)
        if classification is None:
            return None
        category, reason = classification
        return self.quarantine(path, category, reason)

    def stats(self) -> dict:
        counts = {name: 0 for name in self.CATEGORIES.values()}
        total = 0
        if self.root_path.exists():
            for category_name in counts:
                folder = self.root_path / category_name
                if not folder.exists():
                    continue
                count = sum(1 for item in folder.rglob('*') if item.is_file())
                counts[category_name] = count
                total += count
        return {
            "total": total,
            "categories": counts,
            "root_path": str(self.root_path),
            "log_path": str(self.log_path),
        }

    @staticmethod
    def _unique_destination(path: Path) -> Path:
        if not path.exists():
            return path
        counter = 1
        while True:
            candidate = path.with_name(f"{path.stem} ({counter}){path.suffix}")
            if not candidate.exists():
                return candidate
            counter += 1

    @staticmethod
    def _sha256(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open('rb') as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b''):
                digest.update(block)
        return digest.hexdigest()

    def _append_log(self, item: RejectedDocument) -> None:
        self.root_path.mkdir(parents=True, exist_ok=True)
        new_file = not self.log_path.exists()
        with self.log_path.open('a', encoding='utf-8-sig', newline='') as stream:
            writer = csv.writer(stream)
            if new_file:
                writer.writerow(['fecha','archivo','categoria','motivo','ruta_original','ruta_destino','tamano_bytes','sha256'])
            writer.writerow([
                datetime.now().isoformat(timespec='seconds'),
                item.source_path.name,
                item.category,
                item.reason,
                str(item.source_path),
                str(item.destination_path),
                item.size,
                item.sha256,
            ])
