from __future__ import annotations

import logging
from pathlib import Path
from unittest.mock import Mock, patch

from search.embedding_service import EmbeddingService


def test_windows_incomplete_cache_is_quarantined_and_retried(
    tmp_path: Path,
) -> None:
    cache = tmp_path / "fastembed_cache"
    cache.mkdir()
    (cache / "partial.bin").write_bytes(b"incomplete")

    service = object.__new__(EmbeddingService)
    service.model_name = (
        "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
    )
    service.model_cache_path = cache
    service.logger = logging.getLogger(__name__)
    service._model = None
    loaded_model = Mock()

    with (
        patch("search.embedding_service.sys.platform", "win32"),
        patch(
            "search.embedding_service.TextEmbedding",
            side_effect=[
                RuntimeError(
                    "NO_SUCHFILE: model_optimized.onnx File doesn't exist"
                ),
                loaded_model,
            ],
        ) as constructor,
    ):
        assert service.model is loaded_model

    assert constructor.call_count == 2
    assert cache.is_dir()
    quarantined = list(tmp_path.glob("fastembed_cache.incompleta-*"))
    assert len(quarantined) == 1
    assert (quarantined[0] / "partial.bin").read_bytes() == b"incomplete"
