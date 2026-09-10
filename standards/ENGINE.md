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

## Regla canónica, apariciones y fallos

`standards` conserva cada aparición extraída con su redacción, voz,
tratamiento, cita, página y documento. `canonical_standards` representa la
regla consolidada y `standard_occurrences` vincula ambas capas. Por eso una
regla puede tener varias formulaciones y estar respaldada por varios fallos sin
perder trazabilidad.

La consolidación es conservadora:

- las diferencias exclusivamente tipográficas se agrupan automáticamente;
- una relación `duplicate_of` confirmada o auditada se agrupa;
- una `duplicate_of` sólo propuesta permanece separada y se muestra en la UI
  como «Posible misma regla» hasta que el usuario la confirme o rechace;
- `specializes`, `exception_to`, `contradicts`, `supports` y `related_to`
  siguen siendo relaciones entre estándares, no fusiones.

Para migrar una base anterior se ejecuta primero en simulación y luego con
escritura:

```text
python tools/consolidar_estandares_canonicos.py
python tools/consolidar_estandares_canonicos.py --apply
```

Las importaciones V5 y la aplicación de nuevas decisiones de relaciones
actualizan esta capa automáticamente. El proceso es idempotente y no modifica
ni elimina las apariciones originales.

## Revisión de estándares reservados

Una aparición está almacenada pero reservada cuando todavía no cumple
`review_status=validated` y `publication_status=ready|published`. La interfaz
muestra el inventario completo y permite abrir una bandeja de revisión con el
fallo, la cita, la página, la voz y el tratamiento.

Las decisiones disponibles son:

- `publish`: valida la aparición y la deja lista para el diccionario;
- `reserve`: conserva sus estados actuales y registra que fue revisada;
- `reject`: la excluye del producto sin borrar el registro ni su trazabilidad.

Cada decisión queda en `standard_publication_decisions`. Después de publicar o
rechazar se reconstruye la capa canónica dentro de la misma transacción; no se
realiza ninguna llamada a la API ni se reextrae el fallo.

La publicación exige al menos una cita literal no vacía y una página positiva.
La bandeja permite agregar o corregir esa evidencia sin sobrescribir la cita
extraída por V5: la versión humana se guarda como `manual_review` y la edición
queda auditada en `standard_citation_decisions`.

## Formas de ingresar estándares

Hay dos vías complementarias:

1. **Carga manual inmediata.** «Nuevo estándar» recibe la regla, el fallo, la
   voz, el tratamiento y la evidencia. Con cita y página queda visible; si la
   evidencia está incompleta se almacena como reservado. Esta vía no consume
   API.
2. **Extracción por lotes V5.** Cada fallo puede producir cero, una o varias
   apariciones. Los fallos nuevos se acumulan en una cola y se preparan juntos
   cuando alcanzan el umbral operativo; el envío a la API siempre requiere una
   acción explícita. Después de validar citas, las apariciones se comparan con
   el diccionario y sólo los pares candidatos pasan al clasificador de
   relaciones, evitando comparaciones de todos contra todos.

La interfaz de incorporación deberá ofrecer para cada fallo nuevo «Extraer
ahora», «Agregar a la cola» o «No extraer». La opción recomendada será la cola,
con cierre por cantidad de fallos y por límite de tokens; el tamaño inicial de
referencia es 250 fallos. El contenido documental se procesa una sola vez por
huella y los resultados intermedios quedan reanudables en
`runtime/standards/runs/<run-id>`.
