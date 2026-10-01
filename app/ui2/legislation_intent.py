"""Local recognition of normative searches, independent of an article number."""
import re
import unicodedata


_KINDS = (
    ("ley", r"\b(?:ley|leyes)\b"),
    ("código", r"\bcodigos?\b"),
    ("decreto", r"\bdecretos?\b"),
    ("ordenanza", r"\bordenanzas?\b"),
    ("resolución", r"\bresoluci(?:on|ones)\b"),
    ("disposición", r"\bdisposici(?:on|ones)\b"),
    ("reglamento", r"\breglamentos?\b"),
    ("reglamentación", r"\breglamentaci(?:on|ones)\b"),
    ("legislación", r"\blegislaci(?:on|ones)\b"),
    ("constitución", r"\bconstituci(?:on|ones)\b"),
    ("acordada", r"\bacordadas?\b"),
    ("circular", r"\bcircular(?:es)?\b"),
    ("estatuto", r"\bestatutos?\b"),
    ("tratado", r"\btratados?\b"),
    ("convenio", r"\bconvenios?\b"),
    ("norma", r"\bnorm(?:as?|ativa|ativas)\b"),
    ("orden ministerial", r"\borden(?:es)? ministerial(?:es)?\b"),
    ("instrucción general", r"\binstrucci(?:on|ones) general(?:es)?\b"),
    ("decisión administrativa", r"\bdecisi(?:on|ones) administrativas?\b"),
    ("digesto", r"\bdigestos?\b"),
    ("texto ordenado", r"\btextos? ordenados?\b"),
)


def expand_normative_abbreviations(query: str) -> str:
    raw = str(query or "")
    boolean = bool(re.search(r"\b(?:AND|OR|NOT|NEAR(?:/\d+)?)\b|[()]", raw, flags=re.I))
    parts = re.split(r'("[^"]*")', raw)
    for index, part in enumerate(parts):
        for pattern, replacement in (
            (r"\bR\s*\.?\s*G\.?(?!\w)", "resolución general"),
            (r"\bD\s*\.?\s*N\s*\.?\s*U\.?(?!\w)", "decreto de necesidad y urgencia"),
        ):
            value = '"' + replacement + '"' if boolean and index % 2 == 0 else replacement
            part = re.sub(pattern, value, part, flags=re.I)
        parts[index] = part
    return "".join(parts)


def legislation_query_intent(query: str) -> list[str]:
    text = expand_normative_abbreviations(query)
    normalized = "".join(char for char in unicodedata.normalize("NFKD", text) if not unicodedata.combining(char)).casefold()
    return [kind for kind, pattern in _KINDS if re.search(pattern, normalized)]


def is_legislation(category: str) -> bool:
    normalized = "".join(char for char in unicodedata.normalize("NFKD", str(category or "")) if not unicodedata.combining(char)).strip().casefold()
    return normalized == "legislacion"
