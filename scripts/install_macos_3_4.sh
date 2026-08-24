#!/bin/zsh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DATA_ROOT="$HOME/Library/Application Support/LexIA"
LIBRARY_ROOT="$HOME/Documents/LexIA Biblioteca"
CONFIG_PATH="$DATA_ROOT/lexia.local.json"
QDRANT_CONTAINER="lexia-qdrant"
QDRANT_IMAGE="qdrant/qdrant:v1.16.3"
QDRANT_STORAGE="$DATA_ROOT/qdrant"

if ! command -v brew >/dev/null 2>&1; then
  print -u2 "Homebrew no está disponible. Instalalo primero desde https://brew.sh"
  exit 1
fi

if ! brew list --versions python@3.11 >/dev/null 2>&1; then
  brew install python@3.11
fi

if ! command -v docker >/dev/null 2>&1; then
  print "Instalando Docker Desktop para Apple Silicon..."
  brew install --cask docker
fi

print "Iniciando Docker Desktop..."
open -a Docker

for attempt in {1..90}; do
  if docker info >/dev/null 2>&1; then
    break
  fi
  if (( attempt == 90 )); then
    print -u2 "Docker Desktop aún no está listo."
    print -u2 "Aceptá sus términos y esperá a que indique Engine running; luego ejecutá nuevamente este instalador."
    exit 1
  fi
  sleep 2
done

PYTHON_BIN="$(brew --prefix python@3.11)/bin/python3.11"
if [[ ! -x "$PYTHON_BIN" ]]; then
  print -u2 "No se encontró Python 3.11 de Homebrew."
  exit 1
fi

mkdir -p "$DATA_ROOT" "$LIBRARY_ROOT"   "$DATA_ROOT/runtime" "$DATA_ROOT/logs"   "$DATA_ROOT/exports" "$DATA_ROOT/backups"   "$DATA_ROOT/Rejected Documents" "$QDRANT_STORAGE"

"$PYTHON_BIN" - "$CONFIG_PATH" "$LIBRARY_ROOT" "$DATA_ROOT" <<'PY'
import json
import sys
from pathlib import Path

config_path = Path(sys.argv[1])
library_root = sys.argv[2]
data_root = sys.argv[3]
defaults = {
    "library_path": library_root,
    "runtime_path": f"{data_root}/runtime",
    "logs_path": f"{data_root}/logs",
    "exports_path": f"{data_root}/exports",
    "backups_path": f"{data_root}/backups",
    "rejected_documents_path": f"{data_root}/Rejected Documents",
}
try:
    current = json.loads(config_path.read_text(encoding="utf-8"))
except (OSError, json.JSONDecodeError):
    current = {}
if not isinstance(current, dict):
    current = {}
defaults.update(current)
defaults["qdrant_mode"] = "server"
defaults["qdrant_url"] = "http://127.0.0.1:6333"
config_path.write_text(
    json.dumps(defaults, ensure_ascii=False, indent=2) + "\n",
    encoding="utf-8",
)
PY

if docker container inspect "$QDRANT_CONTAINER" >/dev/null 2>&1; then
  docker start "$QDRANT_CONTAINER" >/dev/null 2>&1 || true
else
  docker run --detach     --name "$QDRANT_CONTAINER"     --restart unless-stopped     --publish 127.0.0.1:6333:6333     --publish 127.0.0.1:6334:6334     --volume "$QDRANT_STORAGE:/qdrant/storage"     "$QDRANT_IMAGE" >/dev/null
fi

if [[ "$(docker inspect --format '{{.State.Running}}' "$QDRANT_CONTAINER")" != "true" ]]; then
  print -u2 "No se pudo iniciar Qdrant en Docker. Revisá: docker logs $QDRANT_CONTAINER"
  exit 1
fi

if [[ ! -x "$ROOT/.venv/bin/python" ]]; then
  "$PYTHON_BIN" -m venv "$ROOT/.venv"
fi

"$ROOT/.venv/bin/python" -m pip install --upgrade pip wheel
"$ROOT/.venv/bin/python" -m pip install -r "$ROOT/requirements.txt"
"$ROOT/.venv/bin/python" "$ROOT/verify_installation.py"

chmod +x "$ROOT/INICIAR_LEXIA_MAC.command"   "$ROOT/app/ui2/INICIAR_LEXIA_UI2.command"   "$ROOT/app/ui2/iniciar_lexia_ui2.sh"

print
print "LexIA quedó instalada para macOS."
print "Biblioteca vacía: $LIBRARY_ROOT"
print "Datos internos:   $DATA_ROOT"
print "Qdrant Docker:    $QDRANT_CONTAINER"
print "Para abrirla: doble clic en INICIAR_LEXIA_MAC.command"
