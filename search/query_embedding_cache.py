from __future__ import annotations

import hashlib
import sqlite3
import threading
from pathlib import Path

import numpy as np


class QueryEmbeddingCache:
    """
    Caché persistente de embeddings de consulta.

    Clave:
      model_name + texto normalizado

    Persiste entre reinicios y evita recalcular expansiones jurídicas
    recurrentes del Query Interpreter 2.0.
    """

    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._memory = {}
        self.hits = 0
        self.misses = 0
        self._ensure_schema()

    def _connect(self):
        connection = sqlite3.connect(
            self.path,
            timeout=10,
        )
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA synchronous=NORMAL")
        return connection

    def _ensure_schema(self):
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS query_embeddings (
                    cache_key TEXT PRIMARY KEY,
                    model_name TEXT NOT NULL,
                    query_text TEXT NOT NULL,
                    dimension INTEGER NOT NULL,
                    vector BLOB NOT NULL
                )
                """
            )

    @staticmethod
    def normalize(query):
        return " ".join(str(query or "").split()).strip()

    @classmethod
    def key(cls, model_name, query):
        normalized = cls.normalize(query)
        payload = f"{model_name}\n{normalized}".encode("utf-8")
        return hashlib.sha256(payload).hexdigest()

    def get(self, model_name, query):
        cache_key = self.key(model_name, query)

        with self._lock:
            vector = self._memory.get(cache_key)
            if vector is not None:
                self.hits += 1
                return vector.copy()

            with self._connect() as connection:
                row = connection.execute(
                    """
                    SELECT dimension, vector
                    FROM query_embeddings
                    WHERE cache_key = ?
                    """,
                    (cache_key,),
                ).fetchone()

            if not row:
                self.misses += 1
                return None

            dimension, blob = row
            vector = np.frombuffer(
                blob,
                dtype=np.float32,
                count=int(dimension),
            ).copy()

            self._memory[cache_key] = vector
            self.hits += 1
            return vector.copy()

    def put(self, model_name, query, vector):
        array = np.asarray(
            vector,
            dtype=np.float32,
        ).reshape(-1)

        cache_key = self.key(model_name, query)
        normalized = self.normalize(query)

        with self._lock:
            self._memory[cache_key] = array.copy()

            with self._connect() as connection:
                connection.execute(
                    """
                    INSERT INTO query_embeddings (
                        cache_key,
                        model_name,
                        query_text,
                        dimension,
                        vector
                    )
                    VALUES (?, ?, ?, ?, ?)
                    ON CONFLICT(cache_key) DO UPDATE SET
                        dimension = excluded.dimension,
                        vector = excluded.vector
                    """,
                    (
                        cache_key,
                        str(model_name),
                        normalized,
                        int(array.shape[0]),
                        array.tobytes(),
                    ),
                )

        return array.copy()

    def stats(self):
        with self._connect() as connection:
            count = connection.execute(
                "SELECT COUNT(*) FROM query_embeddings"
            ).fetchone()[0]

        return {
            "entries": int(count),
            "memory_entries": len(self._memory),
            "hits": int(self.hits),
            "misses": int(self.misses),
        }
