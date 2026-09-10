"""Conservative repairs for deterministic legacy text-encoding damage."""

from __future__ import annotations

import re


# Some old Argentine PDFs expose Windows-1252 character bytes through a CP850
# font map.  The resulting substitutions are one character wide and therefore
# can be repaired without changing fragment offsets.
_CP850_TO_WINDOWS = str.maketrans({
    "┴": "Á", "╔": "É", "═": "Í", "Ë": "Ó", "┌": "Ú",
    "ß": "á", "Ú": "é", "Ý": "í", "¾": "ó", "·": "ú",
    "Ð": "Ñ", "±": "ñ", "▄": "Ü", "³": "ü",
    "┐": "¿", "║": "º", "░": "°",
    "½": "«", "╗": "»", "ô": "“", "ö": "”",
    "æ": "‘", "Æ": "’", "û": "–", "ù": "—", "à": "…",
})

_STRONG_CP850_MARKERS = frozenset("┴╔═┌▄║░┐╗")
_WEAK_CP850_MARKERS = frozenset("ËßÚÝ¾·Ð±³½ôöæÆûùà")


def looks_like_legacy_cp850_mojibake(value: str) -> bool:
    """Return True only when the text has convincing CP850 mojibake signs."""
    text = str(value or "")
    if not text:
        return False
    if any(char in text for char in _STRONG_CP850_MARKERS):
        return True

    # Weak markers can be real in foreign-language material. Require several
    # occurrences, at least two distinct forms, and letter adjacency typical
    # of damaged Spanish words (interposici¾n, acompa±arß, tambiÚn).
    adjacent = re.findall(
        r"(?<=[A-Za-zÁÉÍÓÚÜÑáéíóúüñ])"
        r"[ËßÚÝ¾·Ð±³½ôöæÆûùà]"
        r"|[ËßÚÝ¾·Ð±³½ôöæÆûùà]"
        r"(?=[A-Za-zÁÉÍÓÚÜÑáéíóúüñ])",
        text,
    )
    return len(adjacent) >= 3 and len(set(adjacent)) >= 2


def translate_legacy_cp850_mojibake(value: str) -> str:
    """Apply the known one-to-one CP850-to-Windows character mapping."""
    return str(value or "").translate(_CP850_TO_WINDOWS)


def repair_legacy_cp850_mojibake(value: str) -> str:
    """Repair *value* when corruption is detected; otherwise preserve it."""
    text = str(value or "")
    if not looks_like_legacy_cp850_mojibake(text):
        return text
    return translate_legacy_cp850_mojibake(text)
