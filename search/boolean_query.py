from __future__ import annotations

import re
from dataclasses import dataclass


BINARY_OPERATORS = {"AND", "OR", "NOT"}

TOKEN_RE = re.compile(
    r'"[^"]*"'
    r'|\('
    r'|\)'
    r'|\bNEAR(?:/\d+)?\b'
    r'|\bAND\b'
    r'|\bOR\b'
    r'|\bNOT\b'
    r'|[^\s()]+',
    re.IGNORECASE,
)


class BooleanQuerySyntaxError(ValueError):
    pass


@dataclass(frozen=True)
class BooleanQuery:
    original: str
    fts_query: str
    semantic_text: str
    explicit: bool
    rpn: tuple[str, ...] = ()
    atoms: tuple[str, ...] = ()


def _operator(token: str) -> str | None:
    upper = str(token).upper()

    if upper in BINARY_OPERATORS:
        return upper

    if re.fullmatch(r"NEAR(?:/\d+)?", upper):
        return upper

    return None


def _precedence(token: str) -> int:
    op = _operator(token)

    if op and op.startswith("NEAR"):
        return 4

    return {
        "NOT": 3,
        "AND": 2,
        "OR": 1,
    }.get(op or "", 0)


def has_explicit_boolean_syntax(query: str) -> bool:
    raw = str(query or "")

    return bool(
        re.search(
            r"\b(?:AND|OR|NOT|NEAR(?:/\d+)?)\b",
            raw,
            flags=re.IGNORECASE,
        )
        or "(" in raw
        or ")" in raw
    )


def _fts_quote(value: str) -> str:
    return '"' + str(value).replace('"', '""') + '"'


def _tokenize(raw: str) -> list[str]:
    tokens = TOKEN_RE.findall(raw)

    compact_raw = re.sub(r"\s+", "", raw)
    compact_tokens = re.sub(
        r"\s+",
        "",
        "".join(tokens),
    )

    if compact_raw != compact_tokens:
        raise BooleanQuerySyntaxError(
            "La consulta contiene una expresión que no pudo interpretarse."
        )

    return tokens


def _to_rpn(tokens: list[str]) -> tuple[str, ...]:
    output: list[str] = []
    operators: list[str] = []

    for token in tokens:
        op = _operator(token)

        if op:
            while (
                operators
                and _operator(operators[-1])
                and _precedence(operators[-1])
                >= _precedence(op)
            ):
                output.append(operators.pop())

            operators.append(op)
            continue

        if token == "(":
            operators.append(token)
            continue

        if token == ")":
            while (
                operators
                and operators[-1] != "("
            ):
                output.append(
                    operators.pop()
                )

            if not operators:
                raise BooleanQuerySyntaxError(
                    "Hay un paréntesis de cierre sin apertura."
                )

            operators.pop()
            continue

        output.append(token)

    while operators:
        op = operators.pop()

        if op in {"(", ")"}:
            raise BooleanQuerySyntaxError(
                "Hay paréntesis sin cerrar."
            )

        output.append(op)

    return tuple(output)


def parse_boolean_query(query: str) -> BooleanQuery:
    raw = str(query or "").strip()

    if not raw:
        raise BooleanQuerySyntaxError(
            "La consulta está vacía."
        )

    if not has_explicit_boolean_syntax(raw):
        return BooleanQuery(
            original=raw,
            fts_query="",
            semantic_text=raw,
            explicit=False,
        )

    tokens = _tokenize(raw)

    output: list[str] = []
    atoms: list[str] = []
    semantic_parts: list[str] = []

    depth = 0
    expect_operand = True

    for token in tokens:
        op = _operator(token)

        if token == "(":
            if not expect_operand:
                raise BooleanQuerySyntaxError(
                    "Falta un operador antes del paréntesis."
                )

            depth += 1
            output.append("(")
            continue

        if token == ")":
            if expect_operand:
                raise BooleanQuerySyntaxError(
                    "El paréntesis de cierre está en una posición inválida."
                )

            depth -= 1

            if depth < 0:
                raise BooleanQuerySyntaxError(
                    "Hay un paréntesis de cierre sin apertura."
                )

            output.append(")")
            expect_operand = False
            continue

        if op:
            if expect_operand:
                raise BooleanQuerySyntaxError(
                    f"El operador {op} está en una posición inválida."
                )

            if op.startswith("NEAR/"):
                distance = int(
                    op.split("/", 1)[1]
                )

                if not 1 <= distance <= 1000:
                    raise BooleanQuerySyntaxError(
                        "La distancia de NEAR debe estar entre 1 y 1000."
                    )

            output.append(op)
            expect_operand = True
            continue

        if not expect_operand:
            raise BooleanQuerySyntaxError(
                "Falta AND, OR, NOT o NEAR entre dos términos o frases."
            )

        if (
            token.startswith('"')
            and token.endswith('"')
        ):
            value = token[1:-1].strip()
        else:
            value = token.strip()

        if not value:
            raise BooleanQuerySyntaxError(
                "No se admite un término o frase vacía."
            )

        atom = _fts_quote(value)

        output.append(atom)
        atoms.append(atom)
        semantic_parts.append(value)
        expect_operand = False

    if depth:
        raise BooleanQuerySyntaxError(
            "Hay paréntesis sin cerrar."
        )

    if expect_operand:
        raise BooleanQuerySyntaxError(
            "La consulta termina con un operador booleano."
        )

    return BooleanQuery(
        original=raw,
        fts_query=" ".join(output),
        semantic_text=" ".join(
            semantic_parts
        ),
        explicit=True,
        rpn=_to_rpn(output),
        atoms=tuple(
            dict.fromkeys(atoms)
        ),
    )
