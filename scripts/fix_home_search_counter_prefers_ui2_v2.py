from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "app" / "ui2" / "backend.py"

OLD = '''                # Prefer a table containing query/title/objective.
                selected = tables[0]
                selected_cols = []
                for table in tables:
                    cols = [r[1] for r in con.execute(f'PRAGMA table_info("{table}")').fetchall()]
                    lowered = {c.lower() for c in cols}
                    if {"query", "created_at"} & lowered or "query" in lowered:
                        selected, selected_cols = table, cols
                        break
'''

NEW = '''                # Prefer the active UI2 search history table when reading
                # runtime/search_history.sqlite3 for the Inicio counter.
                # Older tables may remain in the same sqlite file and otherwise
                # get selected first, leaving the visible counter stuck.
                selected = tables[0]
                selected_cols = []
                preferred_tables = []
                if path.name == "search_history.sqlite3":
                    preferred_tables.extend([
                        "ui2_search_history_v2",
                        "ui2_search_history",
                        "search_history",
                    ])
                preferred_tables.extend(tables)

                for table in preferred_tables:
                    if table not in tables:
                        continue
                    cols = [r[1] for r in con.execute(f'PRAGMA table_info("{table}")').fetchall()]
                    lowered = {c.lower() for c in cols}
                    if {"query", "created_at"} & lowered or "query" in lowered:
                        selected, selected_cols = table, cols
                        break
'''


def main() -> None:
    if not BACKEND.exists():
        raise SystemExit(f"No existe {BACKEND}")

    text = BACKEND.read_text(encoding="utf-8", errors="replace")
    if "ui2_search_history_v2" in text and "leaving the visible counter stuck" in text:
        print("OK: el parche ya estaba aplicado en backend.py")
        return

    if OLD not in text:
        raise SystemExit("No encontré el bloque esperado en backend.py. No modifiqué nada.")

    backup = BACKEND.with_suffix(".py.bak-home-search-counter-ui2-v2")
    if not backup.exists():
        backup.write_text(text, encoding="utf-8")

    text = text.replace(OLD, NEW, 1)
    BACKEND.write_text(text, encoding="utf-8")
    print("OK: parche aplicado en app/ui2/backend.py")
    print(f"Backup: {backup}")


if __name__ == "__main__":
    main()
