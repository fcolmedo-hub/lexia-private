#!/bin/zsh
set -euo pipefail

service_name="LexIA OpenAI API"
account_name="${USER:-$(id -un)}"
model_name="gpt-5.6-terra"

echo "Configuración segura de OpenAI para LexIA"
echo "La clave anterior será reemplazada después de validar la nueva."
read -rs "openai_key?Pegá tu OPENAI_API_KEY y presioná Enter: "
echo

if [[ -z "${openai_key}" ]]; then
  echo "No se ingresó ninguna clave."
  exit 1
fi

if ! print -r -- "header = \"Authorization: Bearer ${openai_key}\"" | \
  /usr/bin/curl --config - --fail --silent --show-error \
  --connect-timeout 15 --max-time 30 \
  --output /dev/null \
  "https://api.openai.com/v1/models/${model_name}"; then
  unset openai_key
  echo "La clave no pudo validarse con OpenAI. No se modificó el Llavero."
  exit 1
fi

/usr/bin/security add-generic-password \
  -U \
  -a "${account_name}" \
  -s "${service_name}" \
  -w "${openai_key}" \
  >/dev/null

stored_key="$(/usr/bin/security find-generic-password \
  -a "${account_name}" -s "${service_name}" -w)"
if [[ "${stored_key}" != "${openai_key}" ]]; then
  unset openai_key stored_key
  echo "No se pudo verificar la clave en el Llavero."
  exit 1
fi

unset openai_key stored_key
echo "Conexión correcta. OPENAI_API_KEY actualizada para LexIA."
echo "Cerrá completamente LexIA y volvé a abrirla."
