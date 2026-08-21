from pathlib import Path

from core.duplicate_detector import DuplicateDetector


class FakeCatalog:
    def find_path_by_hash(
        self,
        content_hash: str,
        exclude_path: str | None = None,
    ) -> str | None:
        if content_hash == "abc":
            return "data/Jurisprudencia/original.pdf"
        return None


def test_duplicate_detector_returns_original() -> None:
    detector = DuplicateDetector(FakeCatalog())

    original = detector.find_original(
        "abc",
        Path("data/Jurisprudencia/copia.pdf"),
    )

    assert original == "data/Jurisprudencia/original.pdf"
