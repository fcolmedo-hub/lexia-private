"""Exact statutory references, shared by search and the document locator."""
import re
import unicodedata


ARTICLE_WORD = r"(?:art(?:[íi]culo)?s?|art[yý]culo|art═culo)"
SUFFIXES = r"bis|ter|quater|quinquies|sexies|septies|octies|nonies|decies"
NUMBER_LABEL = r"(?:n(?:[úu]mero|ro|o)?\.?\s*[°ºo]?\s*)?"
ARTICLE_NUMBER = r"(?:\d{1,3}(?:\.\d{3})+|\d+)"


def normalize(value):
    return "".join(
        c for c in unicodedata.normalize("NFKD", str(value or ""))
        if not unicodedata.combining(c)
    ).casefold()


def article_reference(value):
    match = re.search(
        rf"\b{ARTICLE_WORD}\.?\s*{NUMBER_LABEL}"
        rf"(?P<number>{ARTICLE_NUMBER})(?!\d)\s*[º°]?"
        rf"(?:\s*(?P<suffix>{SUFFIXES})\b)?",
        str(value or ""), re.I,
    )
    if not match:
        return None
    return {"article": match["number"].replace(".", ""),
            "suffix": (match["suffix"] or "").lower()}


def law_number(value):
    match = re.search(
        rf"\bley\s*{NUMBER_LABEL}(?P<number>{ARTICLE_NUMBER})(?!\d)",
        str(value or ""), re.I,
    )
    return match["number"].replace(".", "") if match else ""


def article_matches(text, intent, headings_only=False):
    """Preserve original offsets; distinguish 5, 50, 5 bis and 5 ter."""
    raw = str(text or "")
    digits = str(intent.get("article") or "")
    if not digits.isdigit():
        return []
    number = re.escape(digits)
    if len(digits) > 3:
        grouped = f"{int(digits):,}".replace(",", ".")
        number = rf"(?:{number}|{re.escape(grouped)})"
    suffix = str(intent.get("suffix") or "")
    pattern = rf"\b{ARTICLE_WORD}\.?\s*{NUMBER_LABEL}{number}(?!\d|\.\d)"
    pattern += r"[º°║]?"
    if suffix:
        pattern += rf"\s*{re.escape(suffix)}\b"
    else:
        pattern += rf"(?![º°║]?\s*(?:{SUFFIXES})\b)"
    pattern += r"(?![a-záéíóúñ])"
    found = []
    for match in re.finditer(pattern, raw, re.I):
        line_start = max(raw.rfind("\n", 0, match.start()),
                         raw.rfind("\f", 0, match.start())) + 1
        prefix = raw[line_start:match.start()].strip(" \t\r-–—•#")
        following = raw[match.end():].split("\n", 1)[0]
        # A contents entry is not the body of the article.
        contents_entry = bool(re.search(r"\.{3,}\s*\d+\s*$", following))
        heading = (not prefix or bool(re.match(r"\s*\.\s*[-–—]", following))) and not contents_entry
        if not headings_only or heading:
            found.append((match, heading))
    return found


def article_excerpt(text, intent, max_chars=520, headings_only=False):
    raw = str(text or "")
    matches = article_matches(raw, intent, headings_only)
    if not matches:
        return ""
    match, _ = max(matches, key=lambda pair: (pair[1], -pair[0].start()))
    end = min(len(raw), match.start() + max(120, int(max_chars or 520)))
    following = re.search(
        rf"[\n\f]\s*{ARTICLE_WORD}\.?\s*{NUMBER_LABEL}\d+",
        raw[match.end():end], re.I,
    )
    truncated = end < len(raw)
    if following:
        end = match.end() + following.start()
        truncated = False
    excerpt = re.sub(r"\s+", " ", raw[match.start():end]).strip()
    return excerpt + (" …" if truncated else "")


def instrument_in_text(text, intent):
    if intent.get("instrument_kind") == "law":
        # Do not join unrelated numbers or match law 70550 when asking for 7055.
        return any(
            law_number(match.group()) == intent.get("law_number")
            for match in re.finditer(
                rf"\bley\s*{NUMBER_LABEL}{ARTICLE_NUMBER}(?!\d)", str(text or ""), re.I
            )
        )
    words = [w for w in str(intent.get("code_name") or "").split()
             if w not in {"de", "del", "la", "las", "los", "y"}]
    normalized = normalize(text)
    return bool(words and re.search(r"\bc[oó]digo\b", normalized)
                and all(re.search(rf"\b{re.escape(w)}\b", normalized) for w in words))


def instrument_in_filename(name, path, intent):
    # The containing directory may identify an instrument, but citations inside
    # another law must not turn that law into the requested primary source.
    components = [name, *re.split(r"[\\/]", str(path or ""))]
    return any(instrument_in_text(component, intent) for component in components)
