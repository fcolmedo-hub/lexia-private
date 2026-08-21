# LexIA Prompt Protocol 2.0

## 1. Objeto

LPP 2.0 define el formato ejecutable de los expedientes `.lexia`.
Su finalidad es impedir que el modelo trate el archivo como un adjunto
pasivo o solicite una nueva consigna.

## 2. Estados

- `RUNNING`: la tarea debe comenzar inmediatamente.
- No existen estados `WAITING` ni `READY` en archivos exportados.

## 3. Capas obligatorias

1. Bootstrap.
2. Perfil de compatibilidad.
3. Runtime.
4. Protocolo de evidencia.
5. Cuerpo jurídico.
6. Control silencioso.
7. Cierre.

## 4. Evidencia

Toda afirmación derivada del expediente debe indicar `[FUENTE N]`.
El modelo no puede usar Internet, memoria o conocimiento externo para
completar información faltante.

## 5. Insuficiencia

La fórmula obligatoria es:

> Las fuentes suministradas no permiten responder este punto.

## 6. Validación

Un archivo no se exporta cuando:

- falta una sección obligatoria;
- el índice y los bloques de fuentes no coinciden;
- se referencia una fuente inexistente;
- la numeración no es continua;
- se detecta una orden activa de consultar Internet;
- se detecta una orden activa de responder en inglés.

## 7. Compatibilidad

La versión inicial contiene perfiles para ChatGPT, Claude, Gemini y un
perfil genérico. El contenido jurídico permanece idéntico; solo cambia
el preámbulo de ejecución.
