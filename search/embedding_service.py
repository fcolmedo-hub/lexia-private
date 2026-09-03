import json
import logging
import sys
import time
from pathlib import Path
from typing import Iterable

import numpy as np
from fastembed import TextEmbedding

from config.settings import SETTINGS
from search.query_embedding_cache import QueryEmbeddingCache


class EmbeddingService:
    def __init__(
        self,
        runtime_path: str | Path = SETTINGS.runtime_path,
    ):
        self.runtime_path = Path(runtime_path)
        self.runtime_path.mkdir(parents=True, exist_ok=True)
        self.model_info_path = self.runtime_path / "embedding_model.json"
        # En Windows, %TEMP% puede borrar parcialmente la caché de FastEmbed y
        # dejar snapshots sin model_optimized.onnx. Una caché persistente dentro
        # del runtime evita que una investigación falle por esa limpieza.
        self.model_cache_path = (
            self.runtime_path / "fastembed_cache"
            if sys.platform == "win32"
            else None
        )
        if self.model_cache_path is not None:
            self.model_cache_path.mkdir(parents=True, exist_ok=True)
        self.logger = logging.getLogger(__name__)

        self.model_name = self._resolve_model_name()
        self.logger.info(
            "Modelo de embeddings seleccionado: %s",
            self.model_name,
        )
        # El modelo ocupa CPU/RAM. Se carga solo en la primera busqueda o
        # indexacion real, nunca al abrir Biblioteca, OCR o Configuracion.
        self._model = None
        self.query_cache = QueryEmbeddingCache(
            self.runtime_path / "query_embedding_cache.sqlite3"
        )

    @property
    def model(self) -> TextEmbedding:
        if self._model is None:
            self.logger.info("Cargando modelo de embeddings: %s", self.model_name)
            self._model = self._load_model()
        return self._model

    def _load_model(self) -> TextEmbedding:
        kwargs = {"model_name": self.model_name}
        if self.model_cache_path is not None:
            kwargs["cache_dir"] = str(self.model_cache_path)

        try:
            return TextEmbedding(**kwargs)
        except Exception as exc:
            if not self._is_recoverable_windows_cache_error(exc):
                raise

            quarantined = self._quarantine_model_cache()
            self.logger.warning(
                "Caché incompleta de FastEmbed apartada en %s; "
                "se reintentará una descarga limpia.",
                quarantined,
            )
            return TextEmbedding(**kwargs)

    def _is_recoverable_windows_cache_error(self, exc: Exception) -> bool:
        if self.model_cache_path is None or sys.platform != "win32":
            return False
        detail = str(exc).casefold()
        return any(
            marker in detail
            for marker in (
                "no_suchfile",
                "file doesn't exist",
                "local file sizes do not match",
                "model_optimized.onnx",
            )
        )

    def _quarantine_model_cache(self) -> Path:
        assert self.model_cache_path is not None
        source = self.model_cache_path
        stamp = time.strftime("%Y%m%d-%H%M%S")
        target = source.with_name(f"{source.name}.incompleta-{stamp}")
        suffix = 1
        while target.exists():
            target = source.with_name(
                f"{source.name}.incompleta-{stamp}-{suffix}"
            )
            suffix += 1

        if source.exists():
            source.replace(target)
        else:
            target.mkdir(parents=True, exist_ok=True)
        source.mkdir(parents=True, exist_ok=True)
        return target

    def _resolve_model_name(self) -> str:
        if self.model_info_path.exists():
            saved = json.loads(
                self.model_info_path.read_text(encoding="utf-8")
            )
            return saved["model_name"]

        supported = {
            item["model"]
            for item in TextEmbedding.list_supported_models()
        }

        for candidate in SETTINGS.preferred_embedding_models:
            if candidate in supported:
                self._save_model_name(candidate)
                return candidate

        multilingual_candidates = sorted(
            model
            for model in supported
            if "multilingual" in model.lower()
        )

        if multilingual_candidates:
            selected = multilingual_candidates[0]
            self._save_model_name(selected)
            return selected

        raise RuntimeError(
            "FastEmbed no informó ningún modelo multilingüe compatible."
        )

    def _save_model_name(self, model_name: str) -> None:
        self.model_info_path.write_text(
            json.dumps(
                {"model_name": model_name},
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

    def embed_passages(
        self,
        texts: Iterable[str],
    ) -> list[np.ndarray]:
        prepared = [
            self._prefix_passage(text)
            for text in texts
        ]
        return list(
            self.model.embed(
                prepared,
                batch_size=SETTINGS.embedding_batch_size,
            )
        )

    def embed_query(self, query: str) -> np.ndarray:
        cached = self.query_cache.get(
            self.model_name,
            query,
        )
        if cached is not None:
            return cached

        vector = list(
            self.model.query_embed(
                [self._prefix_query(query)]
            )
        )[0]

        return self.query_cache.put(
            self.model_name,
            query,
            vector,
        )

    def query_cache_stats(self) -> dict:
        return self.query_cache.stats()

    def dimension(self) -> int:
        probe = self.embed_query("consulta jurídica")
        return int(probe.shape[0])

    def _prefix_passage(self, text: str) -> str:
        if "e5" in self.model_name.lower():
            return f"passage: {text}"
        return text

    def _prefix_query(self, text: str) -> str:
        if "e5" in self.model_name.lower():
            return f"query: {text}"
        return text
