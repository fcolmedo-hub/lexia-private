"""Tribunales informados expresamente al preparar un lote de estándares."""

from __future__ import annotations

import csv
from pathlib import Path


def load_courts(paths: list[str], *, court: str | None = None, courts_file: Path | None = None) -> dict[str, str]:
    if bool(court is not None) == bool(courts_file is not None):
        raise ValueError("Indicá --court o --courts-file para el lote.")
    selected = {path.casefold(): path for path in paths}
    if court is not None:
        value = court.strip()
        if not value:
            raise ValueError("El tribunal del lote no puede estar vacío.")
        return {path: value for path in paths}

    assert courts_file is not None
    with courts_file.open("r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        if reader.fieldnames != ["document_path", "court"]:
            raise ValueError("El CSV debe tener las columnas document_path,court, en ese orden.")
        assigned: dict[str, str] = {}
        for number, row in enumerate(reader, start=2):
            path = str(row.get("document_path") or "").strip()
            tribunal = str(row.get("court") or "").strip()
            if not path or not tribunal or None in row:
                raise ValueError(f"Ruta o tribunal inválido en la línea {number} del CSV.")
            key = path.casefold()
            if key not in selected:
                raise ValueError(f"El fallo de la línea {number} no está en la selección: {path}")
            if key in assigned:
                raise ValueError(f"El fallo está repetido en el CSV: {path}")
            assigned[key] = tribunal
    missing = [path for path in paths if path.casefold() not in assigned]
    if missing:
        raise ValueError("Faltan tribunales para estos fallos:\n" + "\n".join(f"- {path}" for path in missing[:20]))
    return {path: assigned[path.casefold()] for path in paths}


def metadata_with_court(original: dict, court: str) -> dict:
    metadata = {key: value for key, value in original.items()
                if str(key).casefold() not in {"court", "tribunal"}}
    metadata["court"] = court
    metadata["_lexia_court_source"] = "batch_input"
    return metadata
