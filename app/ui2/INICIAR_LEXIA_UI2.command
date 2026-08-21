#!/bin/zsh
set -e
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
PY="$ROOT/.venv/bin/python"
if [ ! -x "$PY" ]; then
  echo "No se encontró $PY"
  read "?Presioná Enter para cerrar..."
  exit 1
fi
cd "$ROOT"
exec "$PY" "$SCRIPT_DIR/launch_ui2.py"
