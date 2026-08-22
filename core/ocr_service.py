from __future__ import annotations

import atexit
import json
import subprocess
import sys
import tempfile
import threading
import time
import weakref
from pathlib import Path
from typing import Callable

from config.settings import SETTINGS


class OCRService:
    """Ejecuta RapidOCR fuera de Streamlit para permitir timeout y cancelacion."""

    _instances: weakref.WeakSet = weakref.WeakSet()

    def __init__(self):
        self._process = None
        self._lock = threading.RLock()
        self.__class__._instances.add(self)

    @classmethod
    def cancel_all(cls) -> None:
        for instance in list(cls._instances):
            instance.cancel_active()

    def cancel_active(self) -> None:
        with self._lock:
            process = self._process
        if process is not None and process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                process.kill()

    @staticmethod
    def _current_pdf_page(
        page_numbers: list[int],
        completed: int,
    ) -> int:
        """Return the actual PDF page currently being processed."""
        if not page_numbers:
            return 0
        index = min(max(int(completed or 0), 0), len(page_numbers) - 1)
        return int(page_numbers[index])

    def extract_pdf_pages(
        self,
        path: str | Path,
        page_numbers: list[int],
        progress_callback: Callable[[int, int], None] | None = None,
        total_pages: int | None = None,
    ) -> dict[int, str]:
        if not page_numbers:
            return {}
        worker = Path(__file__).with_name("ocr_worker.py")
        output = tempfile.NamedTemporaryFile(
            prefix="lexia_ocr_", suffix=".jsonl", delete=False
        )
        output_path = Path(output.name)
        output.close()
        command = [
            sys.executable, str(worker), str(Path(path).resolve()),
            json.dumps(page_numbers), str(int(SETTINGS.ocr_dpi)), str(output_path),
        ]
        creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        process = subprocess.Popen(
            command,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            text=True,
            creationflags=creationflags,
        )
        with self._lock:
            self._process = process
        results: dict[int, str] = {}
        offset = 0
        completed = 0
        document_total = max(
            max(int(page) for page in page_numbers),
            int(total_pages or 0),
        )

        def publish_current_page() -> None:
            """Report the real PDF page being scanned, not a page counter."""
            if not progress_callback:
                return
            progress_callback(
                self._current_pdf_page(page_numbers, completed),
                document_total,
            )
        page_timeout = max(
            15, int(getattr(SETTINGS, "ocr_page_timeout_seconds", 120))
        )
        deadline = time.monotonic() + page_timeout
        next_heartbeat = 0.0
        try:
            while process.poll() is None:
                if output_path.exists():
                    with output_path.open("r", encoding="utf-8") as stream:
                        stream.seek(offset)
                        for line in stream:
                            item = json.loads(line)
                            results[int(item["page"])] = str(item.get("text", ""))
                            completed += 1
                            deadline = time.monotonic() + page_timeout
                            publish_current_page()
                        offset = stream.tell()
                now = time.monotonic()
                if progress_callback and now >= next_heartbeat:
                    publish_current_page()
                    next_heartbeat = now + 1.0
                if now > deadline:
                    raise TimeoutError(
                        f"OCR excedio {page_timeout} segundos en la pagina "
                        f"{page_numbers[min(completed, len(page_numbers) - 1)]}."
                    )
                time.sleep(0.2)

            # Consume el ultimo resultado escrito antes de finalizar.
            if output_path.exists():
                with output_path.open("r", encoding="utf-8") as stream:
                    stream.seek(offset)
                    for line in stream:
                        item = json.loads(line)
                        results[int(item["page"])] = str(item.get("text", ""))
                        completed += 1
                        publish_current_page()
            stderr = process.stderr.read().strip() if process.stderr else ""
            if process.returncode != 0:
                raise RuntimeError(stderr or "El trabajador OCR fue interrumpido.")
            return results
        finally:
            self.cancel_active()
            with self._lock:
                self._process = None
            output_path.unlink(missing_ok=True)


atexit.register(OCRService.cancel_all)
