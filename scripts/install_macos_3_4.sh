#!/bin/zsh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DATA_ROOT="$HOME/Library/Application Support/LexIA"
LIBRARY_ROOT="$HOME/Documents/LexIA Biblioteca"
CONFIG_PATH="$DATA_ROOT/lexia.local.json"

if ! command -v brew >/dev/null 2>&1; then
  print -u2 "Homebrew no está disponible. Instalalo primero desde https://brew.sh"
  exit 1
fi

if ! brew list --versions python@3.11 >/dev/null 2>&1; then
  brew install python@3.11
fi

PYTHON_BIN="$(brew --prefix python@3.11)/bin/python3.11"
if [[ ! -x "$PYTHON_BIN" ]]; then
  print -u2 "No se encontró Python 3.11 de Homebrew."
  exit 1
fi

mkdir -p "$DATA_ROOT" "$LIBRARY_ROOT" \
  "$DATA_ROOT/runtime" "$DATA_ROOT/logs" \
  "$DATA_ROOT/exports" "$DATA_ROOT/backups" \
  "$DATA_ROOT/Rejected Documents"

if [[ ! -f "$CONFIG_PATH" ]]; then
  cat > "$CONFIG_PATH" <<EOF
{
  "library_path": "$LIBRARY_ROOT",
  "runtime_path": "$DATA_ROOT/runtime",
  "logs_path": "$DATA_ROOT/logs",
  "exports_path": "$DATA_ROOT/exports",
  "backups_path": "$DATA_ROOT/backups",
  "rejected_documents_path": "$DATA_ROOT/Rejected Documents",
  "qdrant_mode": "local"
}
EOF
fi

if [[ ! -x "$ROOT/.venv/bin/python" ]]; then
  "$PYTHON_BIN" -m venv "$ROOT/.venv"
fi

"$ROOT/.venv/bin/python" -m pip install --upgrade pip wheel
"$ROOT/.venv/bin/python" -m pip install -r "$ROOT/requirements.txt"
"$ROOT/.venv/bin/python" "$ROOT/verify_installation.py"

chmod +x "$ROOT/INICIAR_LEXIA_MAC.command" \
  "$ROOT/app/ui2/INICIAR_LEXIA_UI2.command" \
  "$ROOT/app/ui2/iniciar_lexia_ui2.sh"

print
print "LexIA quedó instalada para macOS."
print "Biblioteca vacía: $LIBRARY_ROOT"
print "Datos internos:   $DATA_ROOT"
print "Para abrirla: doble clic en INICIAR_LEXIA_MAC.command"
