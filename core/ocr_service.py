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

    def extract_pdf_pages(
        self,
        path: str | Path,
        page_numbers: list[int],
        progress_callback: Callable[[int, int], None] | None = None,
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
                            if progress_callback:
                                progress_callback(completed, len(page_numbers))
                        offset = stream.tell()
                now = time.monotonic()
                if progress_callback and now >= next_heartbeat:
                    progress_callback(completed, len(page_numbers))
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
                        if progress_callback:
                            progress_callback(completed, len(page_numbers))
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
