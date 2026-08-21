# -*- coding: utf-8 -*-
from __future__ import annotations

import os
import sqlite3
import threading
import time
from pathlib import Path

FAST_SEARCH_MIN_DOCUMENTS = 10
FAST_SEARCH_PROBE_MIN_LIMIT = 60
FAST_SEARCH_NAMES_REFRESH_SECONDS = 30.0

def _feature_enabled(root: Path) -> bool:
    env = os.environ.get("LEXIA_FAST_SEARCH")
    if env is not None:
        return env.strip().lower() not in {"0", "false", "off", "no"}
    return (root / "runtime" / "fast_search_1_0" / "enabled").exists()

def _norm_query(value: str) -> str:
    return " ".join(str(value or "").strip().split()).casefold()

def _safe_fts_terms(value: str) -> str:
    clean = str(value or "").strip().strip('"').strip()
    if not clean:
        return ""
    tokens = [
        token.strip(" \t\r\n\"'()[]{}:,;")
        for token in clean.replace("\\", " ").replace("/", " ").split()
    ]
    tokens = [t for t in tokens if t]
    return " ".join('"' + t.replace('"', '""') + '"' for t in tokens)

class FastSearchCatalogProxy:
    def __init__(self, catalog, root: str | Path):
        self._catalog = catalog
        self._root = Path(root).resolve()
        self._state = threading.local()
        self._name_lock = threading.RLock()
        runtime_dir = self._root / "runtime" / "fast_search_1_0"
        runtime_dir.mkdir(parents=True, exist_ok=True)
        self._name_db = runtime_dir / "document_names_fts.sqlite3"
        self._last_refresh_check = 0.0
        self._indexed_catalog_mtime_ns = None

    def __getattr__(self, name):
        return getattr(self._catalog, name)

    def prepare(self, query: str, limit: int, category: str | None = None) -> None:
        if not _feature_enabled(self._root):
            self.clear()
            return
        probe_limit = max(FAST_SEARCH_PROBE_MIN_LIMIT, max(1, int(limit)) * 3)
        try:
            rows = self._catalog.lexical_search(query, probe_limit, category)
        except Exception:
            rows = []
        unique_docs = {
            str(row.get("document_path", "")).casefold()
            for row in rows if row.get("document_path")
        }
        self._state.active = True
        self._state.original = _norm_query(query)
        self._state.category = category
        self._state.probe_rows = rows
        self._state.unique_docs = len(unique_docs)
        self._state.allow_expansions = len(unique_docs) < FAST_SEARCH_MIN_DOCUMENTS

    def clear(self) -> None:
        self._state.active = False
        self._state.original = None
        self._state.category = None
        self._state.probe_rows = None
        self._state.unique_docs = 0
        self._state.allow_expansions = True

    def lexical_search(self, query: str, limit: int, category: str | None = None) -> list[dict]:
        if not bool(getattr(self._state, "active", False)):
            return self._catalog.lexical_search(query, limit, category)
        if _norm_query(query) == getattr(self._state, "original", ""):
            rows = list(getattr(self._state, "probe_rows", []) or [])
            if category:
                rows = [r for r in rows if str(r.get("category", "")) == str(category)]
            return rows[: max(1, int(limit))]
        if not bool(getattr(self._state, "allow_expansions", True)):
            return []
        return self._catalog.lexical_search(query, limit, category)

    def _catalog_path(self) -> Path:
        value = getattr(self._catalog, "database_path", None)
        if value is None:
            raise RuntimeError("DocumentCatalog no expone database_path.")
        return Path(value)

    def _needs_name_refresh(self) -> bool:
        now = time.monotonic()
        if self._name_db.exists() and now - self._last_refresh_check < FAST_SEARCH_NAMES_REFRESH_SECONDS:
            return False
        self._last_refresh_check = now
        catalog_path = self._catalog_path()
        try:
            mtime_ns = catalog_path.stat().st_mtime_ns
        except OSError:
            return not self._name_db.exists()
        if self._name_db.exists() and self._indexed_catalog_mtime_ns is None:
            self._indexed_catalog_mtime_ns = mtime_ns
            return False
        return not self._name_db.exists() or self._indexed_catalog_mtime_ns != mtime_ns

    def _refresh_names(self) -> None:
        with self._name_lock:
            if not self._needs_name_refresh():
                return
            catalog_path = self._catalog_path()
            temp = self._name_db.with_suffix(".sqlite3.tmp")
            if temp.exists():
                temp.unlink()
            src = sqlite3.connect(catalog_path.resolve().as_uri() + "?mode=ro", uri=True)
            src.row_factory = sqlite3.Row
            dst = sqlite3.connect(temp)
            try:
                dst.execute("PRAGMA journal_mode=OFF")
                dst.execute("PRAGMA synchronous=OFF")
                dst.execute("""
                    CREATE VIRTUAL TABLE names_fts USING fts5(
                        document_path UNINDEXED,
                        document_name,
                        category UNINDEXED,
                        tokenize='unicode61 remove_diacritics 2'
                    )
                """)
                rows = src.execute("""
                    SELECT path, name, category
                    FROM documents
                    WHERE COALESCE(is_deleted,0)=0
                      AND name IS NOT NULL
                      AND trim(name) <> ''
                """)
                dst.executemany(
                    "INSERT INTO names_fts(document_path, document_name, category) VALUES (?,?,?)",
                    ((r["path"], r["name"], r["category"]) for r in rows),
                )
                dst.commit()
            finally:
                src.close()
                dst.close()
            temp.replace(self._name_db)
            try:
                self._indexed_catalog_mtime_ns = catalog_path.stat().st_mtime_ns
            except OSError:
                self._indexed_catalog_mtime_ns = None

    def _name_paths(self, query: str, limit: int, category: str | None) -> list[str]:
        self._refresh_names()
        fts_query = _safe_fts_terms(query)
        if not fts_query or not self._name_db.exists():
            return []
        con = sqlite3.connect(self._name_db.resolve().as_uri() + "?mode=ro", uri=True)
        con.row_factory = sqlite3.Row
        try:
            sql = "SELECT document_path FROM names_fts WHERE names_fts MATCH ?"
            params = [fts_query]
            if category:
                sql += " AND category = ?"
                params.append(category)
            sql += " ORDER BY bm25(names_fts) LIMIT ?"
            params.append(max(1, int(limit)))
            return [str(r["document_path"]) for r in con.execute(sql, params).fetchall()]
        except sqlite3.OperationalError:
            return []
        finally:
            con.close()

    def direct_document_search(self, query: str, limit: int = 25, category: str | None = None) -> list[dict]:
        if not _feature_enabled(self._root):
            return self._catalog.direct_document_search(query, limit, category)
        clean = str(query or "").strip()
        if not clean:
            return []
        try:
            paths = self._name_paths(clean, limit, category)
        except Exception:
            return self._catalog.direct_document_search(query, limit, category)
        if not paths:
            return []
        con = sqlite3.connect(self._catalog_path().resolve().as_uri() + "?mode=ro", uri=True)
        con.row_factory = sqlite3.Row
        try:
            placeholders = ",".join("?" for _ in paths)
            sql = f"""
                SELECT d.path, d.name, d.category, d.metadata_json,
                    COALESCE(
                        (SELECT f.text_content FROM fragments f
                         WHERE f.document_path=d.path
                         ORDER BY f.fragment_index LIMIT 1),
                        d.text_content, ''
                    ) AS text_content,
                    0 AS fragment_index,
                    (SELECT f.page_start FROM fragments f
                     WHERE f.document_path=d.path
                     ORDER BY f.fragment_index LIMIT 1) AS page_start,
                    (SELECT f.page_end FROM fragments f
                     WHERE f.document_path=d.path
                     ORDER BY f.fragment_index LIMIT 1) AS page_end
                FROM documents d
                WHERE d.is_deleted=0
                  AND d.path IN ({placeholders})
            """
            params = list(paths)
            if category:
                sql += " AND d.category=?"
                params.append(category)
            rows = [dict(r) for r in con.execute(sql, params).fetchall()]
        finally:
            con.close()
        by_path = {str(r.get("path", "")): r for r in rows}
        return [by_path[p] for p in paths if p in by_path][: max(1, int(limit))]

class FastSearchEngine:
    def __init__(self, delegate, catalog_proxy: FastSearchCatalogProxy):
        self.delegate = delegate
        self.catalog_proxy = catalog_proxy

    def search(self, query: str, limit: int = 20, category: str | None = None, *args, **kwargs):
        if not _feature_enabled(self.catalog_proxy._root):
            return self.delegate.search(query, limit=limit, category=category, *args, **kwargs)
        self.catalog_proxy.prepare(query, limit, category)
        try:
            return self.delegate.search(query, limit=limit, category=category, *args, **kwargs)
        finally:
            self.catalog_proxy.clear()

    def __getattr__(self, name):
        return getattr(self.delegate, name)
