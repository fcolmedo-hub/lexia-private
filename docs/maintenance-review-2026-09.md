# Revisión de Mantenimiento — septiembre de 2026

## Organización

| Acceso | Uso | Decisión |
|---|---|---|
| Estado y actividad | Progreso de AutoSync, últimos archivos, incidencias e historial | Conservar; eliminar el resumen genérico que repetía la misma operación. |
| AutoSync | Modo manual, automático o programado; sincronización manual | Conservar separado de OCR; ver aquí también archivos y progreso. |
| OCR | Archivos pendientes, en proceso o con errores; abrir, seleccionar, reprocesar y eliminar | Darle una pestaña propia con lista de altura disponible y scroll interno. |
| Duplicados | Revisar original y copia, eliminar explícitamente el duplicado | Conservar la pestaña estable del cambio anterior. |
| Copias | Copias operativas de bases y configuración | Conservar y explicar el alcance: no reemplazan un respaldo de la biblioteca física ni del índice Qdrant. |
| Avanzado → Diagnóstico | Comprobar componentes, disco y bases | Conservar bajo demanda; las incidencias se muestran en Estado, sin duplicarlas aquí. |
| Avanzado → Monitor técnico | Registros para resolver fallos | Conservar fuera de la navegación principal. |
| Avanzado → Acerca de LexIA | Versiones y configuración para soporte | Conservar fuera de la navegación principal. |

No se encontraron operaciones de mantenimiento que sea prudente eliminar por inútiles. La confusión provenía de la mezcla de configuración y trabajo sobre archivos, resúmenes repetidos y herramientas técnicas al mismo nivel que las tareas habituales. Se preservan los comandos y las confirmaciones de eliminación física.

## Comportamiento

- AutoSync publica progreso por etapa: exploración, comparación de ubicaciones, actualización de rutas, extracción, índice y vínculos. Durante la exploración informa archivos revisados sin inventar un total. Un porcentaje corresponde a una etapa, no al tiempo total restante.
- Lista acotada de hasta 50 operaciones recientes informadas por el servicio, con origen y destino cuando hay reubicación. No es un historial exhaustivo de todos los documentos.
- Los eventos nuevos no reemplazan el contador de un lote en curso. Los movimientos de carpetas solicitan reconciliación. Los archivos auxiliares de macOS/Windows y los temporales de Office no se tratan como documentos.
- Historial, OCR, Monitor y listas conservan su scroll al actualizar. La entrada a OCR no desplaza la página; carga pendientes directamente.
- OCR usa filas compactas con rutas truncadas y texto completo en tooltip. Solo la lista se desplaza. Las pestañas toman los estilos calculados de las pestañas reales de Buscar, como Investigación.
- El nombre Biblioteca del árbol actualiza el árbol y los documentos sin pasar por el enrutador antiguo. El checkbox y la flecha mantienen sus funciones.

## Validación

Pruebas sobre archivos temporales, respuestas simuladas y navegador Chromium. No se ejecutó OCR ni se modificó una biblioteca real. Se verifican selección, borrado cancelado/confirmado, paginación, duplicados, scroll, progreso, eventos de carpetas, y ventanas de 1440×900, 1280×720, 1024×768, 390×844 y 1280×650. La comprobación en los contenedores nativos de macOS y Windows queda para la instalación del usuario.

Pruebas de interfaz: desde `tests/maintenance_ui`, `npm install`, `npx playwright install chromium`, `npm test`, `npm run test:layout`. El test de layout también acepta `LEXIA_PLAYWRIGHT_MODULE` y `LEXIA_CHROMIUM_PATH` para usar un navegador local existente.
