from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(slots=True)
class ContextSelectionStats:
    ranked_candidates: int
    selected: int
    distinct_documents: int
    distinct_categories: int
    near_duplicates_skipped: int
    same_document_skipped: int


class IntelligentContextSelector:
    def __init__(self, max_per_document=2, similarity_threshold=0.88):
        self.max_per_document = max(1, int(max_per_document))
        self.similarity_threshold = float(similarity_threshold)
        self.last_stats = ContextSelectionStats(0, 0, 0, 0, 0, 0)

    def select(self, ranked, limit):
        ranked = list(ranked or [])
        limit = max(1, int(limit))

        selected = []
        selected_keys = set()
        per_document = {}
        categories = set()
        signatures = []
        near_duplicates = 0
        same_document_skipped = 0

        # Pase 1: documentos distintos, primero categorías nuevas.
        for require_new_category in (True, False):
            for item in ranked:
                if len(selected) >= limit:
                    break

                result = item[1]
                key = self._fragment_key(result)
                if key in selected_keys:
                    continue

                path = self._path_key(result)
                if per_document.get(path, 0) >= 1:
                    continue

                category = self._category_key(result)
                if require_new_category and category and category in categories:
                    continue

                signature = self._signature(getattr(result, "text", ""))
                if self._is_near_duplicate(signature, signatures):
                    near_duplicates += 1
                    continue

                selected.append(item)
                selected_keys.add(key)
                per_document[path] = 1
                if category:
                    categories.add(category)
                signatures.append(signature)

            if len(selected) >= limit:
                break

        # Pase 2: admite un segundo fragmento por documento,
        # evitando fragmentos contiguos si existen alternativas.
        for item in ranked:
            if len(selected) >= limit:
                break

            result = item[1]
            key = self._fragment_key(result)
            if key in selected_keys:
                continue

            path = self._path_key(result)
            if per_document.get(path, 0) >= self.max_per_document:
                same_document_skipped += 1
                continue

            if self._is_adjacent_to_selected(result, selected):
                same_document_skipped += 1
                continue

            signature = self._signature(getattr(result, "text", ""))
            if self._is_near_duplicate(signature, signatures):
                near_duplicates += 1
                continue

            selected.append(item)
            selected_keys.add(key)
            per_document[path] = per_document.get(path, 0) + 1
            category = self._category_key(result)
            if category:
                categories.add(category)
            signatures.append(signature)

        # Pase 3: fallback para completar el límite sin perder cobertura.
        for item in ranked:
            if len(selected) >= limit:
                break

            result = item[1]
            key = self._fragment_key(result)
            if key in selected_keys:
                continue

            path = self._path_key(result)
            if per_document.get(path, 0) >= self.max_per_document:
                continue

            selected.append(item)
            selected_keys.add(key)
            per_document[path] = per_document.get(path, 0) + 1
            category = self._category_key(result)
            if category:
                categories.add(category)

        documents = {self._path_key(item[1]) for item in selected}
        categories = {
            self._category_key(item[1])
            for item in selected
            if self._category_key(item[1])
        }

        self.last_stats = ContextSelectionStats(
            ranked_candidates=len(ranked),
            selected=len(selected),
            distinct_documents=len(documents),
            distinct_categories=len(categories),
            near_duplicates_skipped=near_duplicates,
            same_document_skipped=same_document_skipped,
        )
        return selected

    @staticmethod
    def _path_key(result):
        return str(getattr(result, "document_path", "")).casefold()

    @staticmethod
    def _category_key(result):
        return str(getattr(result, "category", "") or "").strip().casefold()

    @classmethod
    def _fragment_key(cls, result):
        return (
            cls._path_key(result),
            int(getattr(result, "fragment_index", 0) or 0),
        )

    @staticmethod
    def _signature(text):
        words = re.findall(
            r"[a-záéíóúñ0-9]{3,}",
            str(text or "").casefold(),
        )
        return set(words[:350])

    def _is_near_duplicate(self, signature, previous):
        if not signature:
            return False

        for other in previous:
            if not other:
                continue
            union = signature | other
            if not union:
                continue
            similarity = len(signature & other) / len(union)
            if similarity >= self.similarity_threshold:
                return True

        return False

    @classmethod
    def _is_adjacent_to_selected(cls, result, selected):
        path = cls._path_key(result)
        index = int(getattr(result, "fragment_index", 0) or 0)

        for item in selected:
            other = item[1]
            if cls._path_key(other) != path:
                continue

            other_index = int(
                getattr(other, "fragment_index", 0) or 0
            )
            if abs(index - other_index) <= 1:
                return True

        return False
