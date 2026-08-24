#!/bin/zsh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
PYTHON_BIN="$ROOT/.venv/bin/python"
DATA_ROOT="$HOME/Library/Application Support/LexIA"
LOG_DIR="$DATA_ROOT/logs"

if [[ ! -x "$PYTHON_BIN" ]]; then
  print -u2 "LexIA no está instalada. Ejecutá primero scripts/install_macos_3_4.sh"
  read "?Presioná Enter para cerrar..."
  exit 1
fi

mkdir -p "$LOG_DIR"
cd "$ROOT"

"$PYTHON_BIN" "$ROOT/run_lexia.py" > "$LOG_DIR/classic_ui.log" 2>&1 &
CLASSIC_PID=$!

cleanup() {
  kill "$CLASSIC_PID" >/dev/null 2>&1 || true
}
trap cleanup EXIT INT TERM

sleep 3
"$PYTHON_BIN" "$ROOT/app/ui2/launch_ui2.py"
