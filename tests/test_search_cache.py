from pathlib import Path

from storage.search_cache_repository import (
    SearchCacheRepository,
)


def test_search_cache_roundtrip(tmp_path: Path) -> None:
    repository = SearchCacheRepository(
        tmp_path / "cache.sqlite3"
    )

    repository.set(
        "key",
        [{"document_name": "fallo.pdf"}],
    )

    payload = repository.get("key")

    assert payload is not None
    assert payload[0]["document_name"] == "fallo.pdf"
