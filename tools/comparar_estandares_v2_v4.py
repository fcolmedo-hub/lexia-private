from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_response(path: Path) -> list[dict[str, Any]]:
    value = load_json(path)
    if not isinstance(value, list):
        raise RuntimeError(f"La raíz de {path} no es un array")
    return [x for x in value if isinstance(x, dict)]


def statements(rows: list[dict[str, Any]]) -> list[str]:
    return [str(x.get("statement") or "").strip() for x in rows]


def main() -> int:
    p = argparse.ArgumentParser(description="Compara estándares V2 y V4 de un mismo fallo.")
    p.add_argument("--pilot-id", type=int, default=1)
    p.add_argument("--v2", type=Path, default=Path(r"runtime\standards_pilot\batch_luna_v2\results"))
    p.add_argument("--v4", type=Path, default=Path(r"runtime\standards_pilot\batch_luna_v4_test5\results"))
    args = p.parse_args()

    name = f"{args.pilot_id:03d}_respuesta.txt"
    v2_path = args.v2 / name
    v4_path = args.v4 / name
    if not v2_path.exists():
        raise RuntimeError(f"No existe V2: {v2_path}")
    if not v4_path.exists():
        raise RuntimeError(f"No existe V4: {v4_path}")

    v2 = load_response(v2_path)
    v4 = load_response(v4_path)

    print(f"PILOT_ID {args.pilot_id}")
    print(f"V2: {len(v2)} estándares")
    print(f"V4: {len(v4)} estándares")

    print("\n### V2")
    for i, s in enumerate(statements(v2), start=1):
        print(f"{i}. {s}")

    print("\n### V4")
    for i, s in enumerate(statements(v4), start=1):
        print(f"{i}. {s}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
