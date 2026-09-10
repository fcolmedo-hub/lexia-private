from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from services.standards_canonicalizer import rebuild_canonical_groups


DEFAULT_DB = REPO_ROOT / "runtime" / "standards" / "standards.sqlite3"


def consolidate(db_path: Path, *, apply: bool = False) -> dict[str, object]:
    if not db_path.exists():
        raise FileNotFoundError(str(db_path))
    conn = sqlite3.connect(db_path, timeout=10)
    try:
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("BEGIN IMMEDIATE")
        stats = rebuild_canonical_groups(conn)
        result: dict[str, object] = {
            "mode": "apply" if apply else "dry_run",
            "db_path": str(db_path.resolve()),
            **stats,
        }
        if apply:
            conn.commit()
        else:
            conn.rollback()
        return result
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Consolida apariciones validadas en estándares canónicos. "
            "Por defecto sólo simula; --apply escribe las tablas derivadas."
        )
    )
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    print(json.dumps(consolidate(args.db, apply=args.apply), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
