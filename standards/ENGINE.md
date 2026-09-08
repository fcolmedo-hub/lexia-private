# Motor incremental del Diccionario de Estándares

El motor conserva un directorio y un estado por ejecución en
`runtime/standards/runs/<run-id>`. Funciona igual en Windows y macOS y nunca
envía lotes a la API de manera implícita.

## Migración única del piloto

Las bases creadas antes de `relation_decisions` deben registrar una vez las 227
clasificaciones históricas. El comando detecta automáticamente las auditorías
existentes y primero puede ejecutarse sin `--apply` como simulación.

```text
python tools/aplicar_relaciones_estandares.py
python tools/aplicar_relaciones_estandares.py --apply
```

## Nueva incorporación

1. Preparar localmente los fallos seleccionados y el lote V5:

   ```text
   python tools/actualizar_diccionario_estandares.py prepare --paths-file seleccion.txt
   ```

2. Enviar explícitamente la extracción y anotar el `run_id` informado:

   ```text
   python tools/actualizar_diccionario_estandares.py submit-extraction --run-id <run-id>
   ```

3. Consultar el lote y, cuando termine, recogerlo. La recolección valida la
   evidencia por `unit_ids`, importa los estándares y prepara únicamente las
   relaciones todavía no clasificadas:

   ```text
   python tools/actualizar_diccionario_estandares.py batch-status --run-id <run-id>
   python tools/actualizar_diccionario_estandares.py collect-extraction --run-id <run-id>
   ```

4. Si existen relaciones nuevas, enviarlas y recogerlas:

   ```text
   python tools/actualizar_diccionario_estandares.py submit-relations --run-id <run-id>
   python tools/actualizar_diccionario_estandares.py batch-status --run-id <run-id>
   python tools/actualizar_diccionario_estandares.py collect-relations --run-id <run-id>
   ```

`status` no llama a la API. Muestra el estado durable y los conteos de SQLite.
Las relaciones positivas ingresan como `proposed`; las decisiones `none`
también se guardan para evitar reprocesarlas. Si un fallo se reextrae, las
reglas automáticas obsoletas quedan `hidden`, sin eliminar historial ni cargas
manuales.
