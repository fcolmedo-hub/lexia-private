from pathlib import Path

import numpy as np

from search.query_embedding_cache import QueryEmbeddingCache


def test_cache_roundtrip(tmp_path):
    cache = QueryEmbeddingCache(
        tmp_path / "cache.sqlite3"
    )

    vector = np.array(
        [1.0, 2.0, 3.0],
        dtype=np.float32,
    )

    assert cache.get("model", "plazo razonable") is None

    cache.put(
        "model",
        "plazo razonable",
        vector,
    )

    recovered = cache.get(
        "model",
        "  plazo   razonable  ",
    )

    assert np.allclose(
        recovered,
        vector,
    )


def test_cache_separates_models(tmp_path):
    cache = QueryEmbeddingCache(
        tmp_path / "cache.sqlite3"
    )

    cache.put(
        "model-a",
        "consulta",
        np.array([1.0], dtype=np.float32),
    )

    assert cache.get(
        "model-b",
        "consulta",
    ) is None


def test_embedding_service_is_patched():
    source = Path(
        "search/embedding_service.py"
    ).read_text(encoding="utf-8")

    assert "QueryEmbeddingCache" in source
    assert "query_cache.get" in source
    assert "query_cache.put" in source
