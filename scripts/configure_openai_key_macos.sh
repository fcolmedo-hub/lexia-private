#!/bin/zsh
set -euo pipefail

service_name="LexIA OpenAI API"
account_name="${USER:-$(id -un)}"

echo "Configuración segura de OpenAI para LexIA"
read -rs "openai_key?Pegá tu OPENAI_API_KEY y presioná Enter: "
echo

if [[ -z "${openai_key}" ]]; then
  echo "No se ingresó ninguna clave."
  exit 1
fi

/usr/bin/security add-generic-password \
  -U \
  -a "${account_name}" \
  -s "${service_name}" \
  -w "${openai_key}" \
  >/dev/null

stored_key="$(/usr/bin/security find-generic-password -s "${service_name}" -w)"
if [[ "${stored_key}" != "${openai_key}" ]]; then
  unset openai_key stored_key
  echo "No se pudo verificar la clave en el Llavero."
  exit 1
fi

unset openai_key stored_key
echo "OPENAI_API_KEY guardada correctamente para LexIA."
echo "Cerrá y volvé a abrir LexIA para aplicarla."
