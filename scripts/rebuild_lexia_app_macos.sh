#!/bin/zsh
set -euo pipefail

ROOT="${LEXIA_ROOT:-$HOME/LexIA_2.3_DEV}"
PY="$ROOT/.venv/bin/python"
APP="/Applications/LexIA.app"
BUILD_ROOT="$ROOT/.build_lexia_macos"
ICON_OUT="$BUILD_ROOT/LexIA.icns"
ENTRY="$ROOT/app/ui2/macos_desktop.py"

if [[ ! -x "$PY" ]]; then
  echo "No se encontró $PY" >&2
  exit 1
fi
if [[ ! -f "$ENTRY" ]]; then
  echo "No se encontró $ENTRY" >&2
  exit 1
fi

mkdir -p "$BUILD_ROOT"
rm -rf "$BUILD_ROOT/build" "$BUILD_ROOT/dist" "$BUILD_ROOT/LexIA.spec"

# Reutilizar el icono azul ya instalado. No se versionan binarios de iconos.
ICON_SRC=""
if [[ -d "$APP/Contents/Resources" ]]; then
  ICON_SRC="$(find "$APP/Contents/Resources" -maxdepth 1 -type f -name '*.icns' -print -quit 2>/dev/null || true)"
fi
if [[ -n "$ICON_SRC" ]]; then
  cp "$ICON_SRC" "$ICON_OUT"
else
  echo "No se encontró un .icns dentro de $APP/Contents/Resources" >&2
  echo "Conservá instalada la LexIA.app actual antes de ejecutar este script." >&2
  exit 1
fi

if ! "$PY" -m PyInstaller --version >/dev/null 2>&1; then
  echo "Instalando PyInstaller en el entorno virtual de LexIA..."
  "$PY" -m pip install --quiet pyinstaller
fi

cd "$BUILD_ROOT"

"$PY" -m PyInstaller \
  --noconfirm \
  --clean \
  --windowed \
  --name LexIA \
  --icon "$ICON_OUT" \
  --osx-bundle-identifier "ai.lexia.desktop" \
  --hidden-import webview \
  --hidden-import webview.platforms.cocoa \
  --distpath "$BUILD_ROOT/dist" \
  --workpath "$BUILD_ROOT/build" \
  --specpath "$BUILD_ROOT" \
  "$ENTRY"

NEW_APP="$BUILD_ROOT/dist/LexIA.app"
if [[ ! -d "$NEW_APP" ]]; then
  echo "PyInstaller no generó $NEW_APP" >&2
  exit 1
fi

# Firma ad-hoc suficiente para una aplicación local no distribuida.
/usr/bin/codesign --force --deep --sign - "$NEW_APP" >/dev/null 2>&1 || true

BACKUP=""
if [[ -d "$APP" ]]; then
  BACKUP="/Applications/LexIA.app.backup-$(date +%Y%m%d-%H%M%S)"
  mv "$APP" "$BACKUP"
fi

cp -R "$NEW_APP" "$APP"
/usr/bin/xattr -dr com.apple.quarantine "$APP" >/dev/null 2>&1 || true
/usr/bin/codesign --force --deep --sign - "$APP" >/dev/null 2>&1 || true

# Refrescar LaunchServices para que Dock/Finder asocien el bundle real.
LSREGISTER="/System/Library/Frameworks/CoreServices.framework/Frameworks/LaunchServices.framework/Support/lsregister"
if [[ -x "$LSREGISTER" ]]; then
  "$LSREGISTER" -f "$APP" >/dev/null 2>&1 || true
fi

killall Dock >/dev/null 2>&1 || true

echo
echo "LexIA.app instalada correctamente en: $APP"
if [[ -n "$BACKUP" ]]; then
  echo "Copia de seguridad anterior: $BACKUP"
fi
echo "Abrí LexIA desde /Applications o volvé a fijarla en el Dock si fuera necesario."
