#!/bin/zsh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
PYTHON_BIN="$ROOT/.venv/bin/python"
DATA_ROOT="$HOME/Library/Application Support/LexIA"
LOG_DIR="$DATA_ROOT/logs"

if [[ ! -x "$PYTHON_BIN" ]]; then
    print -u2 "LexIA no está instalada correctamente."
    exit 1
fi

mkdir -p "$LOG_DIR"
cd "$ROOT"

# Limpiar únicamente procesos anteriores del runtime UI2 de este checkout.
pkill -f "$ROOT/run_lexia_services.py" >/dev/null 2>&1 || true
pkill -f "$ROOT/app/ui2/server.py" >/dev/null 2>&1 || true
pkill -f "$ROOT/app/ui2/launch_ui2.py" >/dev/null 2>&1 || true
sleep 1

# Servicios internos de LexIA, sin interfaz clásica/Streamlit.
"$PYTHON_BIN" "$ROOT/run_lexia_services.py" \
    > "$LOG_DIR/services_ui2.log" 2>&1 &
SERVICES_PID=$!

cleanup() {
    kill "$SERVICES_PID" >/dev/null 2>&1 || true
}
trap cleanup EXIT INT TERM

# Esperar al bridge local antes de abrir UI2.
BRIDGE_READY=0
for _ in {1..30}; do
    if /usr/sbin/lsof -nP -iTCP:8513 -sTCP:LISTEN >/dev/null 2>&1; then
        BRIDGE_READY=1
        break
    fi
    if ! kill -0 "$SERVICES_PID" >/dev/null 2>&1; then
        print -u2 "Los servicios de LexIA finalizaron durante el arranque."
        print -u2 "Revisá: $LOG_DIR/services_ui2.log"
        exit 1
    fi
    sleep 1
done

if [[ "$BRIDGE_READY" -ne 1 ]]; then
    print -u2 "LexIA no pudo iniciar su puente local de servicios (puerto 8513)."
    print -u2 "Revisá: $LOG_DIR/services_ui2.log"
    exit 1
fi

# Abrir exclusivamente la interfaz UI2.
"$PYTHON_BIN" "$ROOT/app/ui2/launch_ui2.py"
