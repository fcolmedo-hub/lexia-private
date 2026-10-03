"""Filesystem modification dates for the navigator; independent of indexing dates."""
from __future__ import annotations

from collections import OrderedDict
from datetime import datetime, timezone
import math
from pathlib import Path
import stat
from threading import Lock
from time import monotonic


_CACHE_LIMIT = 100_000
_CACHE_SECONDS = 60
_cache: OrderedDict[str, tuple[float, float | None]] = OrderedDict()
_lock = Lock()


def file_modification_timestamp(path: str) -> float | None:
    """Read the original file's last content modification timestamp."""
    key = str(path or "")
    if not key:
        return None
    now = monotonic()
    with _lock:
        cached = _cache.get(key)
        if cached is not None and cached[0] > now:
            _cache.move_to_end(key)
            return cached[1]
    timestamp = None
    try:
        info = Path(key).stat()
        if stat.S_ISREG(info.st_mode):
            value = info.st_mtime
            if value is not None and math.isfinite(float(value)):
                timestamp = float(value)
    except (OSError, ValueError, TypeError, OverflowError):
        pass
    with _lock:
        # Brief negative caching avoids repeated failed stats in a single SQL
        # sort, while newly restored files become visible promptly.
        _cache[key] = (now + (_CACHE_SECONDS if timestamp is not None else 2), timestamp)
        _cache.move_to_end(key)
        while len(_cache) > _CACHE_LIMIT:
            _cache.popitem(last=False)
    return timestamp


def file_date_iso(timestamp: float | None) -> str:
    if timestamp is None:
        return ""
    try:
        return datetime.fromtimestamp(timestamp, timezone.utc).isoformat(timespec="seconds")
    except (OverflowError, OSError, ValueError):
        return ""
