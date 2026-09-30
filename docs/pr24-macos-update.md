# Actualización de Mac al código de PR24

`scripts/install_pr24_macos.py` instala el conjunto fijo de 62 archivos de la
revisión `41b8b70a8acd81f59b42dd5a98241bcee1a0e06f`, comparado con
`b4c3c00b0bf2d54f2c62e9d4bc2fd02ecb5f9efe`. No cambia la rama ni HEAD.

Se revisó el ZIP Mac del 28/09/2026: 15 archivos modificados y tres archivos
nuevos. Nueve de los archivos cruzados ya coinciden con la versión de destino.
`app_runtime.js` combina la actualización con el cargador local de la vista
previa de artículos legales. Las versiones locales exactas de `maintenance.js`
y `windows_maintenance_duplicates.js` se reconocen por SHA256, tras comprobar
que sus diferencias corresponden a las mejoras de PR24. Cualquier otro
contenido conflictivo detiene toda la operación.

## Garantías del instalador

- Comprobación completa antes de escribir; `--check` no escribe archivos.
- Verificación del hash Git de cada archivo de destino.
- Respaldo de archivos reemplazados, modos y manifiesto de hashes en Escritorio.
- Escritura atómica por archivo, restauración si falla una escritura.
- Rechazo de enlaces simbólicos y cambios entre la comprobación y la instalación.
- Conservación de `app/ui2/index.html`, archivos fuera de la lista fija,
  configuración, catálogo, Qdrant y runtime. No migra datos de Windows.
- Ejecuciones sucesivas no reaplican cambios ya incorporados.

Cerrar LexIA antes de instalar. Descargar la rama, extraer el instalador a una
carpeta temporal y ejecutarlo desde el checkout con `.venv/bin/python`, primero
con `--check`. Instalar `openai` en ese entorno si falta: es la dependencia nueva
de PR24. No se hacen solicitudes a la API durante la instalación.

El lanzador Mac suministrado usa `.venv/bin/python` y el código del checkout para
los servicios y assets. Como esta actualización no cambia el lanzador, no se
requiere reconstruir LexIA.app: basta salir completamente y abrirla otra vez.

## Validación

- Seis pruebas unittest sobre repositorios Git temporales: combinación,
  respaldo, idempotencia, conflictos, archivos ausentes, colisiones de archivos
  nuevos, enlaces, cambios concurrentes, permisos, restauración y hashes exactos.
- Simulación con los archivos reales del ZIP y las versiones base/destino:
  53 archivos por actualizar; segunda ejecución sin cambios.
- Sintaxis Python y JavaScript del resultado; preservación byte a byte de
  archivos locales fuera del plan, incluido index.html, y sentinel de runtime.
- No se ejecutó la aplicación gráfica en macOS en este entorno.
