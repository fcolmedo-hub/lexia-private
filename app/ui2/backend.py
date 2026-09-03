from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

from portability import project_root

PROJECT_ROOT = project_root()

try:
    from config.settings import SETTINGS
except Exception:
    SETTINGS = None


def _resolve(value: Any, fallback: str) -> Path:
    path = Path(value if value is not None else fallback)
    if not path.is_absolute():
        path = (PROJECT_ROOT / path).resolve()
    return path


def _setting(name: str, fallback: str) -> Path:
    value = getattr(SETTINGS, name, None) if SETTINGS is not None else None
    return _resolve(value, fallback)


def _ro_connect(path: Path) -> sqlite3.Connection:
    # SQLite URI mode=ro guarantees this UI process cannot modify the DB.
    uri = path.resolve().as_uri() + "?mode=ro"
    con = sqlite3.connect(uri, uri=True, timeout=3)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA query_only = ON")
    return con


def _safe_json(path: Path) -> dict:
    try:
        if not path.exists():
            return {}
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _format_time(value: str) -> str:
    value = str(value or "").strip()
    if not value:
        return ""
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return dt.strftime("%d/%m %H:%M")
    except Exception:
        return value[-16:]


class LiveReadOnlyAdapter:
    """Read-only projection of LexIA runtime state for UI2.

    It never instantiates LexIAApplication, AutoSyncService, DocumentCatalog,
    Qdrant, OCR workers or any migration service.
    """

    def __init__(self) -> None:
        self.catalog_path = _setting("catalog_path", "runtime/lexia_catalog.sqlite3")
        self.runtime_path = _setting("runtime_path", "runtime")
        self.autosync_state_path = _setting(
            "autosync_state_path", "runtime/autosync_state.json"
        )
        self.context_history_path = self.runtime_path / "context_query_history.sqlite3"
        self.search_history_path = self.runtime_path / "search_history.sqlite3"
        self.ocr_path = _setting("ocr_queue_path", "runtime/ocr_queue.sqlite3")

    def _catalog(self) -> dict:
        result = {
            "documents": 0,
            "fragments": 0,
            "added_today": None,
            "categories": [],
            "recent_documents": [],
            "recent_errors": [],
            "ocr_pages": 0,
        }
        if not self.catalog_path.exists():
            return result
        try:
            with _ro_connect(self.catalog_path) as con:
                document_columns = {
                    str(row[1])
                    for row in con.execute('PRAGMA table_info("documents")').fetchall()
                }
                result["documents"] = int(con.execute(
                    "SELECT COUNT(*) FROM documents WHERE COALESCE(is_deleted, 0) = 0"
                ).fetchone()[0])
                if "created_at" in document_columns:
                    result["added_today"] = int(con.execute(
                        """SELECT COUNT(*) FROM documents
                           WHERE COALESCE(is_deleted, 0) = 0
                             AND created_at IS NOT NULL
                             AND date(created_at, 'localtime') = date('now', 'localtime')"""
                    ).fetchone()[0])
                result["fragments"] = int(con.execute(
                    """SELECT COUNT(*)
                       FROM fragments f
                       JOIN documents d ON d.path=f.document_path
                       WHERE COALESCE(d.is_deleted, 0)=0"""
                ).fetchone()[0])

                rows = con.execute(
                    """SELECT category, COUNT(*) n
                       FROM documents
                       WHERE COALESCE(is_deleted, 0)=0
                       GROUP BY category
                       ORDER BY n DESC
                       LIMIT 8"""
                ).fetchall()
                result["categories"] = [
                    {"name": str(r["category"] or "Sin categoría"), "count": int(r["n"])}
                    for r in rows
                ]

                rows = con.execute(
                    """SELECT name,path,category,updated_at,extraction_method,total_pages
                       FROM documents
                       WHERE COALESCE(is_deleted, 0)=0
                         AND (extraction_error IS NULL OR extraction_error='')
                       ORDER BY datetime(updated_at) DESC
                       LIMIT 8"""
                ).fetchall()
                result["recent_documents"] = [
                    {
                        "name": str(r["name"] or ""),
                        "path": str(r["path"] or ""),
                        "category": str(r["category"] or ""),
                        "updated_at": _format_time(r["updated_at"]),
                        "method": str(r["extraction_method"] or ""),
                        "pages": int(r["total_pages"] or 0),
                    }
                    for r in rows
                ]

                rows = con.execute(
                    """SELECT name,path,category,updated_at,extraction_error
                       FROM documents
                       WHERE COALESCE(is_deleted, 0)=0
                         AND extraction_error IS NOT NULL
                         AND extraction_error!=''
                       ORDER BY datetime(updated_at) DESC
                       LIMIT 6"""
                ).fetchall()
                result["recent_errors"] = [
                    {
                        "name": str(r["name"] or ""),
                        "error": str(r["extraction_error"] or ""),
                        "updated_at": _format_time(r["updated_at"]),
                    }
                    for r in rows
                ]

                try:
                    result["ocr_pages"] = int(con.execute(
                        "SELECT COALESCE(SUM(ocr_pages),0) FROM documents WHERE COALESCE(is_deleted, 0)=0"
                    ).fetchone()[0])
                except sqlite3.Error:
                    pass
        except Exception as exc:
            result["error"] = str(exc)
        return result

    @staticmethod
    def _generic_history(path: Path, limit: int = 5) -> dict:
        out = {"count": 0, "today_count": 0, "recent": []}
        if not path.exists():
            return out
        try:
            with _ro_connect(path) as con:
                tables = [
                    r[0] for r in con.execute(
                        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
                    ).fetchall()
                ]
                if not tables:
                    return out
                # search_history.sqlite3 contains legacy and UI2 tables.  The
                # home counter must read the table updated by the current UI.
                selected = tables[0]
                selected_cols = []
                candidates = list(tables)
                if path.name == "search_history.sqlite3":
                    candidates = [
                        "ui2_search_history_v2",
                        "ui2_search_history",
                        "search_history",
                    ] + candidates
                for table in candidates:
                    if table not in tables:
                        continue
                    cols = [r[1] for r in con.execute(f'PRAGMA table_info("{table}")').fetchall()]
                    lowered = {c.lower() for c in cols}
                    if {"query", "created_at"} & lowered or "query" in lowered:
                        selected, selected_cols = table, cols
                        break
                if not selected_cols:
                    selected_cols = [r[1] for r in con.execute(
                        f'PRAGMA table_info("{selected}")'
                    ).fetchall()]
                out["count"] = int(con.execute(
                    f'SELECT COUNT(*) FROM "{selected}"'
                ).fetchone()[0])

                lower = {c.lower(): c for c in selected_cols}
                qcol = lower.get("query") or lower.get("title") or lower.get("prompt")
                ocol = lower.get("objective") or lower.get("mode") or lower.get("category")
                ccol = lower.get("created_at") or lower.get("updated_at") or lower.get("timestamp")
                if ccol:
                    out["today_count"] = int(con.execute(
                        f'''SELECT COUNT(*) FROM "{selected}"
                            WHERE "{ccol}" IS NOT NULL
                              AND date("{ccol}", 'localtime') = date('now', 'localtime')'''
                    ).fetchone()[0])
                if qcol:
                    fields = [qcol]
                    if ocol and ocol not in fields: fields.append(ocol)
                    if ccol and ccol not in fields: fields.append(ccol)
                    select = ", ".join(f'"{c}"' for c in fields)
                    order = (
                        f' ORDER BY "{ccol}" DESC, rowid DESC'
                        if ccol else " ORDER BY rowid DESC"
                    )
                    rows = con.execute(
                        f'SELECT {select} FROM "{selected}"{order} LIMIT ?',
                        (limit,),
                    ).fetchall()
                    for r in rows:
                        item = {"query": str(r[qcol] or "")}
                        if ocol: item["objective"] = str(r[ocol] or "")
                        if ccol: item["created_at"] = _format_time(r[ccol])
                        out["recent"].append(item)
        except Exception as exc:
            out["error"] = str(exc)
        return out

    def _ocr_stats(self) -> dict:
        out = {"pending": 0, "processing": 0, "error": 0}
        if not self.ocr_path.exists():
            return out
        try:
            with _ro_connect(self.ocr_path) as con:
                tables = [
                    r[0] for r in con.execute(
                        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
                    ).fetchall()
                ]
                for table in tables:
                    cols = [r[1] for r in con.execute(
                        f'PRAGMA table_info("{table}")'
                    ).fetchall()]
                    status_col = next((c for c in cols if c.lower() == "status"), None)
                    if not status_col:
                        continue
                    rows = con.execute(
                        f'SELECT "{status_col}", COUNT(*) n FROM "{table}" GROUP BY "{status_col}"'
                    ).fetchall()
                    for r in rows:
                        key = str(r[0] or "").lower()
                        n = int(r[1] or 0)
                        if key in {"pending", "queued", "waiting"}: out["pending"] += n
                        elif key in {"processing", "running", "active"}: out["processing"] += n
                        elif key in {"error", "failed"}: out["error"] += n
                    break
        except Exception:
            pass
        return out

    def snapshot(self) -> dict:
        catalog = self._catalog()
        autosync = _safe_json(self.autosync_state_path)
        context = self._generic_history(self.context_history_path, 5)
        search = self._generic_history(self.search_history_path, 5)
        ocr = self._ocr_stats()

        phase = str(autosync.get("phase", "idle") or "idle")
        status = str(autosync.get("status", "Biblioteca al día") or "Biblioteca al día")
        if phase in {"waiting", "scanning", "indexing", "knowledge"}:
            headline = "Sincronizando"
        elif phase == "error":
            headline = "Atención"
        else:
            headline = "Sincronizado"

        return {
            "ok": True,
            "read_only": True,
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "catalog": catalog,
            "autosync": {
                "phase": phase,
                "status": status,
                "headline": headline,
                "current_file": str(autosync.get("current_file", "") or ""),
                "processed": int(autosync.get("processed", 0) or 0),
                "total": int(autosync.get("total", 0) or 0),
                "percentage": int(autosync.get("percentage", 0) or 0),
                "last_sync": str(autosync.get("last_sync", "") or ""),
                "last_error": str(autosync.get("last_error", "") or ""),
                "pending_changes": bool(autosync.get("pending_changes", False)),
            },
            "ocr": ocr,
            "contexts": context,
            "searches": search,
        }
