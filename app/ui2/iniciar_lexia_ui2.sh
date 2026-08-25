#!/bin/sh
set -eu
SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
PY="$ROOT/.venv/bin/python"
[ -x "$PY" ] || { echo "No se encontró $PY" >&2; exit 1; }
cd "$ROOT"
exec "$PY" "$SCRIPT_DIR/launch_ui2.py"
