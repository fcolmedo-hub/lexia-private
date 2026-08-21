import re
from pathlib import Path

from config.settings import SETTINGS
from models.search_result import SearchResult


class LegalAuthorityRanker:
    COURT_WEIGHTS: tuple[tuple[str, float], ...] = (
        ("corte suprema de justicia de la nación", 1.55),
        ("csjn", 1.55),
        ("suprema corte", 1.42),
        ("superior tribunal", 1.38),
        ("cámara federal", 1.32),
        ("cámara nacional", 1.30),
        ("tribunal fiscal de la nación", 1.28),
        ("cámara de apelación", 1.24),
        ("juzgado federal", 1.14),
        ("juzgado", 1.08),
    )

    def __init__(self):
        self.category_weights = dict(SETTINGS.category_weights)

    def score(self, result: SearchResult) -> float:
        category_weight = self.category_weights.get(
            result.category,
            1.0,
        )

        haystack = (
            f"{result.document_name} {result.text[:1500]}"
        ).lower()

        court_weight = 1.0

        for pattern, weight in self.COURT_WEIGHTS:
            if pattern in haystack:
                court_weight = max(court_weight, weight)

        filename_weight = self._filename_weight(result.document_path)

        return category_weight * court_weight * filename_weight

    def _filename_weight(self, path: Path) -> float:
        name = path.name.lower()

        if re.search(r"\b(csjn|corte suprema)\b", name):
            return 1.20

        if re.search(r"\b(cámara|camara|stj|scj)\b", name):
            return 1.10

        return 1.0
