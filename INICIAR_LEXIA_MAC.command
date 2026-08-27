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

# Docker Desktop/Qdrant: si Docker no está ejecutándose, iniciarlo en segundo
# plano. -g evita activar la aplicación y -j la inicia oculta, para que LexIA
# no muestre la ventana principal de Docker durante su propio arranque.
if ! /usr/bin/pgrep -f "/Applications/Docker.app" >/dev/null 2>&1; then
    /usr/bin/open -gja Docker >/dev/null 2>&1 || true
fi

# Si macOS/Docker muestran alguna ventana durante la inicialización, ocultar
# la aplicación sin interferir con el daemon. Es best-effort: el arranque de
# LexIA no depende de permisos de Automatización/Accesibilidad.
(
    for _ in {1..20}; do
        if /usr/bin/pgrep -f "/Applications/Docker.app" >/dev/null 2>&1; then
            /usr/bin/osascript -e 'tell application "System Events" to set visible of process "Docker Desktop" to false' >/dev/null 2>&1 || \
            /usr/bin/osascript -e 'tell application "System Events" to set visible of process "Docker" to false' >/dev/null 2>&1 || true
        fi
        sleep 1
    done
) >/dev/null 2>&1 &

DOCKER_BIN=""
for candidate in \
    /usr/local/bin/docker \
    /opt/homebrew/bin/docker \
    "$HOME/.docker/bin/docker"
do
    if [[ -x "$candidate" ]]; then
        DOCKER_BIN="$candidate"
        break
    fi
done

DOCKER_READY=0
for _ in {1..90}; do
    if [[ -n "$DOCKER_BIN" ]]; then
        if "$DOCKER_BIN" info >/dev/null 2>&1; then
            DOCKER_READY=1
            break
        fi
    elif /usr/bin/pgrep -f "/Applications/Docker.app" >/dev/null 2>&1; then
        DOCKER_READY=1
        break
    fi
    sleep 1
done

if [[ "$DOCKER_READY" -ne 1 ]]; then
    print -u2 "Docker Desktop no quedó disponible dentro del tiempo esperado."
    exit 1
fi

# Qdrant suele iniciarse junto con Docker Desktop mediante su contenedor
# persistente. Esperar al puerto antes de arrancar LexIA evita fallos de inicio.
QDRANT_READY=0
for _ in {1..90}; do
    if /usr/sbin/lsof -nP -iTCP:6333 -sTCP:LISTEN >/dev/null 2>&1; then
        QDRANT_READY=1
        break
    fi
    sleep 1
done

if [[ "$QDRANT_READY" -ne 1 ]]; then
    print -u2 "Qdrant no quedó disponible en el puerto 6333."
    exit 1
fi

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
