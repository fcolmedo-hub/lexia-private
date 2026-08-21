import html
import re

class ResultHighlighter:
    def highlight(self, text: str, query: str, extra_terms: list[str] | None = None) -> str:
        escaped = html.escape(text)
        terms = [t for t in re.findall(r"[A-Za-zÁÉÍÓÚÑáéíóúñ0-9\.]+", query) if len(t) > 2]
        terms.extend(extra_terms or [])
        for term in sorted(set(terms), key=len, reverse=True)[:20]:
            escaped = re.compile(re.escape(html.escape(term)), re.I).sub(
                lambda m: f"<mark>{m.group(0)}</mark>", escaped
            )
        return escaped.replace("\n", "<br>")
