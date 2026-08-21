from __future__ import annotations

from datetime import datetime, timedelta, timezone

try:
    from zoneinfo import ZoneInfo
except ImportError:
    ZoneInfo = None

UTC = timezone.utc
ARGENTINA_FIXED = timezone(timedelta(hours=-3))

def _argentina_tz():
    if ZoneInfo is not None:
        try:
            return ZoneInfo("America/Argentina/Buenos_Aires")
        except Exception:
            pass
    return ARGENTINA_FIXED

def format_argentina_datetime(value) -> str:
    if value is None:
        return ""
    if isinstance(value, datetime):
        dt = value
    else:
        text = str(value).strip()
        if not text:
            return ""
        normalized = text[:-1] + "+00:00" if text.endswith("Z") else text
        try:
            dt = datetime.fromisoformat(normalized)
        except ValueError:
            parsed = None
            for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M:%S.%f"):
                try:
                    parsed = datetime.strptime(text, fmt)
                    break
                except ValueError:
                    continue
            if parsed is None:
                return text
            dt = parsed
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    argentina = dt.astimezone(_argentina_tz())
    return argentina.strftime("%d/%m/%Y %H:%M:%S")
