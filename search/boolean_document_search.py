from __future__ import annotations

import re
import sqlite3
import unicodedata
from dataclasses import dataclass
from pathlib import Path

from search.boolean_query import BooleanQuery


@dataclass
class _Operand:
    documents: set[str]
    atom: str | None = None


@dataclass
class _NearHit:
    page_start: int | None = None
    page_end: int | None = None


def _normal_path(value: str) -> str:
    return str(value or "").replace("\\", "/").rstrip("/").casefold()


def _inside_folder(path: str, folder: str | None) -> bool:
    if not folder:
        return True
    p = _normal_path(path)
    f = _normal_path(folder)
    return p == f or p.startswith(f + "/")


def _normalize_text(value: str) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(
        ch for ch in text
        if not unicodedata.combining(ch)
    )
    return text.casefold()


def _text_tokens(value: str) -> list[str]:
    return re.findall(
        r"[a-z0-9]+",
        _normalize_text(value),
    )


def _atom_value(atom: str) -> str:
    value = str(atom or "").strip()
    if value.startswith('"') and value.endswith('"'):
        value = value[1:-1]
    return value.replace('""', '"')


def _atom_tokens(atom: str) -> list[str]:
    return _text_tokens(_atom_value(atom))


def _documents_for_match(
    con: sqlite3.Connection,
    match_query: str,
    category: str | None,
    folder: str | None,
) -> set[str]:
    sql = (
        "SELECT DISTINCT f.document_path "
        "FROM fragments_fts AS f "
        "LEFT JOIN documents AS d ON d.path=f.document_path "
        "WHERE fragments_fts MATCH ? "
        "AND COALESCE(d.is_deleted,0)=0 "
    )

    params: list[object] = [match_query]

    if category:
        sql += "AND f.category=? "
        params.append(category)

    rows = con.execute(sql, params).fetchall()

    return {
        str(row[0])
        for row in rows
        if _inside_folder(str(row[0]), folder)
    }


def _phrase_occurrences(
    tokens: list[str],
    phrase: list[str],
) -> list[tuple[int, int]]:
    if not phrase:
        return []

    size = len(phrase)

    return [
        (index, index + size)
        for index in range(
            0,
            len(tokens) - size + 1,
        )
        if tokens[index:index + size] == phrase
    ]


def _occurrence_gap(
    left: tuple[int, int],
    right: tuple[int, int],
) -> int:
    left_start, left_end = left
    right_start, right_end = right

    if left_end <= right_start:
        return right_start - left_end

    if right_end <= left_start:
        return left_start - right_end

    return 0


def _find_near_hit(
    tokens: list[str],
    token_pages: list[int | None],
    left_atom: str,
    right_atom: str,
    distance: int,
) -> _NearHit | None:
    left_phrase = _atom_tokens(left_atom)
    right_phrase = _atom_tokens(right_atom)

    if not left_phrase or not right_phrase:
        return None

    left_hits = _phrase_occurrences(
        tokens,
        left_phrase,
    )
    right_hits = _phrase_occurrences(
        tokens,
        right_phrase,
    )

    best = None

    for left in left_hits:
        for right in right_hits:
            gap = _occurrence_gap(
                left,
                right,
            )

            if gap > distance:
                continue

            start = min(
                left[0],
                right[0],
            )
            end = max(
                left[1],
                right[1],
            ) - 1

            pages = [
                p
                for p in token_pages[start:end + 1]
                if p is not None
            ]

            hit = _NearHit(
                page_start=min(pages) if pages else None,
                page_end=max(pages) if pages else None,
            )

            if best is None:
                best = (gap, hit)
            elif gap < best[0]:
                best = (gap, hit)

    return best[1] if best else None


def _near_distance(operator: str) -> int:
    if operator.upper() == "NEAR":
        return 10

    match = re.fullmatch(
        r"NEAR/(\d+)",
        operator,
        flags=re.IGNORECASE,
    )

    if not match:
        raise ValueError(
            "Operador NEAR inválido."
        )

    return int(match.group(1))


def _documents_for_near(
    con: sqlite3.Connection,
    left_atom: str,
    right_atom: str,
    operator: str,
    category: str | None,
    folder: str | None,
    near_hits: dict[str, _NearHit],
) -> set[str]:

    left_docs = _documents_for_match(
        con,
        left_atom,
        category,
        folder,
    )

    right_docs = _documents_for_match(
        con,
        right_atom,
        category,
        folder,
    )

    candidates = left_docs & right_docs

    if not candidates:
        return set()

    con.execute(
        "DROP TABLE IF EXISTS lexia_near_candidates"
    )

    con.execute(
        """
        CREATE TEMP TABLE lexia_near_candidates (
            document_path TEXT PRIMARY KEY
        )
        """
    )

    con.executemany(
        """
        INSERT INTO lexia_near_candidates(
            document_path
        ) VALUES (?)
        """,
        ((path,) for path in candidates),
    )

    rows = con.execute(
        """
        SELECT
            f.document_path,
            CAST(f.fragment_index AS INTEGER)
                AS fragment_index,
            f.text_content,
            fr.page_start,
            fr.page_end
        FROM fragments_fts AS f
        JOIN lexia_near_candidates AS c
          ON c.document_path=f.document_path
        LEFT JOIN fragments AS fr
          ON fr.document_path=f.document_path
         AND fr.fragment_index=
             CAST(f.fragment_index AS INTEGER)
        ORDER BY
            f.document_path,
            CAST(f.fragment_index AS INTEGER)
        """
    ).fetchall()

    distance = _near_distance(operator)

    accepted: set[str] = set()

    current_path = None
    document_tokens: list[str] = []
    token_pages: list[int | None] = []

    def evaluate_current():
        if not current_path:
            return

        hit = _find_near_hit(
            document_tokens,
            token_pages,
            left_atom,
            right_atom,
            distance,
        )

        if hit is not None:
            accepted.add(current_path)
            near_hits.setdefault(
                current_path,
                hit,
            )

    for row in rows:
        path = str(
            row["document_path"] or ""
        )

        if (
            current_path is not None
            and path != current_path
        ):
            evaluate_current()
            document_tokens = []
            token_pages = []

        current_path = path

        tokens = _text_tokens(
            row["text_content"] or ""
        )

        page = row["page_start"]

        document_tokens.extend(tokens)
        token_pages.extend(
            [page] * len(tokens)
        )

    evaluate_current()

    return accepted


def _evaluate_document_expression(
    con: sqlite3.Connection,
    query: BooleanQuery,
    category: str | None,
    folder: str | None,
    near_hits: dict[str, _NearHit],
) -> set[str]:

    stack: list[_Operand] = []

    for token in query.rpn:
        upper = token.upper()

        near_operator = bool(
            re.fullmatch(
                r"NEAR(?:/\d+)?",
                upper,
            )
        )

        if (
            upper not in {
                "AND",
                "OR",
                "NOT",
            }
            and not near_operator
        ):
            stack.append(
                _Operand(
                    documents=_documents_for_match(
                        con,
                        token,
                        category,
                        folder,
                    ),
                    atom=token,
                )
            )
            continue

        if len(stack) < 2:
            raise ValueError(
                "La expresión booleana no pudo evaluarse."
            )

        right = stack.pop()
        left = stack.pop()

        if near_operator:
            if (
                left.atom is None
                or right.atom is None
            ):
                raise ValueError(
                    "NEAR debe aplicarse entre términos o frases."
                )

            documents = _documents_for_near(
                con,
                left.atom,
                right.atom,
                upper,
                category,
                folder,
                near_hits,
            )

            stack.append(
                _Operand(
                    documents=documents,
                )
            )

        elif upper == "AND":
            stack.append(
                _Operand(
                    documents=(
                        left.documents
                        & right.documents
                    )
                )
            )

        elif upper == "OR":
            stack.append(
                _Operand(
                    documents=(
                        left.documents
                        | right.documents
                    )
                )
            )

        elif upper == "NOT":
            stack.append(
                _Operand(
                    documents=(
                        left.documents
                        - right.documents
                    )
                )
            )

    if len(stack) != 1:
        raise ValueError(
            "La expresión booleana no pudo evaluarse."
        )

    return stack[0].documents


def search_boolean_documents(
    database_path: str | Path,
    query: BooleanQuery,
    limit: int = 20,
    category: str | None = None,
    folder: str | None = None,
) -> list[dict]:

    if not query.explicit:
        raise ValueError(
            "Se requiere una consulta booleana explícita."
        )

    database_path = Path(database_path)
    limit = max(1, int(limit or 20))

    con = sqlite3.connect(
        str(database_path),
        timeout=10,
    )
    con.row_factory = sqlite3.Row

    try:
        near_hits: dict[
            str,
            _NearHit,
        ] = {}

        eligible = _evaluate_document_expression(
            con,
            query,
            category,
            folder,
            near_hits,
        )

        if not eligible:
            return []

        con.execute(
            """
            CREATE TEMP TABLE lexia_boolean_docs (
                document_path TEXT PRIMARY KEY
            )
            """
        )

        con.executemany(
            """
            INSERT INTO lexia_boolean_docs(
                document_path
            ) VALUES (?)
            """,
            ((path,) for path in eligible),
        )

        representative_match = (
            " OR ".join(query.atoms)
        )

        rows = con.execute(
            """
            SELECT
                f.document_path,
                f.fragment_index,
                f.category,
                f.document_name,
                f.text_content,
                snippet(
                    fragments_fts,
                    4,
                    '',
                    '',
                    ' … ',
                    64
                ) AS match_snippet,
                fr.page_start,
                fr.page_end,
                bm25(
                    fragments_fts,
                    1.0
                ) AS lexical_bm25
            FROM fragments_fts AS f
            JOIN lexia_boolean_docs AS e
              ON e.document_path=f.document_path
            LEFT JOIN fragments AS fr
              ON fr.document_path=f.document_path
             AND fr.fragment_index=
                 CAST(f.fragment_index AS INTEGER)
            WHERE fragments_fts MATCH ?
            ORDER BY lexical_bm25 ASC
            LIMIT ?
            """,
            (
                representative_match,
                max(limit * 100, 1000),
            ),
        ).fetchall()

        by_document: dict[str, sqlite3.Row] = {}

        for row in rows:
            path = str(
                row["document_path"] or ""
            )

            if path not in by_document:
                by_document[path] = row

        selected = []

        for path in eligible:
            row = by_document.get(path)

            if row is None:
                continue

            page_start = row["page_start"]
            page_end = row["page_end"]

            near_hit = near_hits.get(path)

            if near_hit is not None:
                page_start = near_hit.page_start
                page_end = near_hit.page_end

            selected.append({
                "document_path": path,
                "document_name": str(
                    row["document_name"]
                    or Path(path).name
                    or "Documento"
                ),
                "category": str(
                    row["category"] or ""
                ),
                "fragment_index": int(
                    row["fragment_index"] or 0
                ),
                "text_content": str(
                    row["match_snippet"]
                    or row["text_content"]
                    or ""
                ),
                "page_start": page_start,
                "page_end": page_end,
                "lexical_bm25":
                    row["lexical_bm25"],
                "near_match":
                    near_hit is not None,
            })

        selected.sort(
            key=lambda item: (
                float(
                    item["lexical_bm25"]
                    or 0.0
                ),
                item["document_name"].lower(),
            )
        )

        return selected[:limit]

    finally:
        con.close()
