<!-- Extraído de SKILL.md por CM2 (auditoría 2026-08-07): bloque
condicional o de consulta que no toda sesión necesita. El SKILL.md deja
un stub con la condición de entrada y apunta aquí. -->

## PASO 5.B — ESCRITURA DE TELEMETRÍA

Si `telemetria` está configurada en `config.yaml`, ejecutar este paso
DESPUÉS de presentar el resumen al usuario y ANTES de cerrar la sesión.

**La telemetría se escribe siempre en `~/.email-triage/`**. Si el directorio
no existe, crearlo con Desktop Commander (`create_directory`). Si alguna
escritura falla, registrar el error en el resumen pero no abortar.

### Archivos y formato

#### `guardar_score: true` → `scores.jsonl`

Una línea JSON por correo procesado en la sesión:

```json
{"session_id":"YYYYMMDD-HHMMSS","ts":"ISO8601","message_id":"<id>","subject":"...","from":"...","tier":"REVIEW","score_final":7,"valor_decisional":3,"calidad_epistemica":2,"riesgo_manipulacion":-1,"coste_cognitivo":-1,"presion_accion":4,"puntos_hard_rules":0}
```

#### `guardar_explicacion: true` → `explicaciones.jsonl`

Una línea JSON por correo con el rationale completo:

```json
{"session_id":"YYYYMMDD-HHMMSS","message_id":"<id>","subject":"...","from":"...","tier":"REVIEW","razones_positivas":["...","...","..."],"razones_negativas":["...","...","..."],"rationale":"..."}
```

#### `guardar_vector: true` → `vectors.jsonl`

Una línea JSON por correo con el vector binario de criterios activados
(1 = criterio activo/aplicado, 0 = no aplica):

```json
{"session_id":"YYYYMMDD-HHMMSS","message_id":"<id>","tier":"REVIEW","score_final":7,"criterios":{"cambia_algo_concreto":1,"cambio_predicciones":1,"sorpresa_bayesiana":0,"evidencia_filtrada":1,"forward_backward_flow":0,"impacto_causal_real":1,"urgencia_real_vs_fabricada":0,"argument_screens_off_authority":1,"hug_the_query":1,"semantic_stopsigns":0,"entangled_truths":1,"absence_of_expected_evidence":0,"distancia_inferencial":0}}
```

#### `guardar_correccion: true` → `correcciones.jsonl`

Solo se escribe cuando el usuario cambia el tier asignado (override). Se registra
en el momento en que el usuario da la corrección, no al final de la sesión:

```json
{"session_id":"YYYYMMDD-HHMMSS","ts":"ISO8601","message_id":"<id>","subject":"...","from":"...","tier_asignado":"ARCHIVE","tier_corregido":"REVIEW","score_final":-2,"rationale_usuario":"(si el usuario da explicación)","simulacion":false}
```

El campo `simulacion` es opcional: su ausencia equivale a `false` (sesión
real). En modo simulación DEBE escribirse a `true` (ver PASO 4.G) — el
PASO 0.B pondera esas correcciones a la mitad.

#### `exportar_mal_clasificados: true` → `mal_clasificados.jsonl`

Alias de las entradas de `correcciones.jsonl` donde `tier_asignado != tier_corregido`.
Se escribe al mismo tiempo que `guardar_correccion`. Permite filtrar rápidamente
los errores del modelo sin parsear todo el log de correcciones.

### Cuándo NO escribir

- Si todos los flags de `telemetria` son `false`, omitir este paso completamente
- No escribir entradas de correos que se saltaron (remitentes en `ignorar`)
- No escribir entradas de correos en modo degradado `[solo metadatos]` en
  `vectors.jsonl` (el vector estaría incompleto y contaminaría el dataset)

### Retención

Los archivos de telemetría crecen indefinidamente. No purgar automáticamente
(a diferencia del session log) — son datos históricos valiosos para el usuario.
Advertir si algún archivo supera 10 MB.

---
