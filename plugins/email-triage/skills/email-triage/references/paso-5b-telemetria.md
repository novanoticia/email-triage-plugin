<!-- Extraído de SKILL.md por CM2 (auditoría 2026-08-07): bloque
condicional o de consulta que no toda sesión necesita. El SKILL.md deja
un stub con la condición de entrada y apunta aquí. -->

## PASO 5.B — ESCRITURA DE TELEMETRÍA

Si `telemetria` está configurada en `config.yaml`, ejecutar este paso
DESPUÉS de presentar el resumen al usuario y ANTES de cerrar la sesión.

**La telemetría se escribe siempre en `~/.email-triage/`**. Si el directorio
no existe, crearlo con Desktop Commander (`create_directory`). Si alguna
escritura falla, registrar el error en el resumen pero no abortar.

### Desglose de una sola pasada (`--desglose` sin `--desglose-append`)

Para conservar el desglose completo sin meterlo al contexto, añade
`--desglose <ruta>` a la misma invocación de `scoring` (combinable con
`--brief`):
`triage_helpers.py scoring --brief --desglose ~/.email-triage/tmp/desglose.json`
escribe el desglose por correo a fichero (JSON, escritura atómica) mientras
stdout sigue compacto; un fallo de escritura se reporta en `desglose_error`,
nunca en silencio (CM2/F12). (Movido desde el SKILL.md en v3.22.17.)

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

**No lo escribas tú** (desde v3.21.19 `registrar` lo rechaza): lo deriva
`vectores` del desglose del scoring de esta sesión, el de
`desgloses/<session_id>.jsonl` o el de `tmp/desglose-<session_id>.jsonl`
(ver PASO 4). Pásale el mapa `id` del scoring → message-id(s) por fichero:

```bash
# ~/.email-triage/tmp/vectores.json:
#   {"session_id": "YYYYMMDD-HHMMSS", "message_ids": {"1": "<mid>", "2": ["<mid-a>", "<mid-b>"]}}
python3 "<ruta-del-skill>/scripts/triage_helpers.py" vectores \
  --desglose ~/.email-triage/tmp/desglose-<session_id>.jsonl \
  --config ~/.email-triage/config.yaml < ~/.email-triage/tmp/vectores.json
```

Si el scoring llevó `--config-veloz` o `--config-ensayo`, pásale a `vectores`
las mismas capas: fijan qué criterios son core.

Escribe una línea por correo (manda la última puntuación de cada id) con
`criterios` (1 = evaluado con veredicto válido, 0 = no evaluado o no aplica)
y `veredictos`. Omite, con motivo en `omitidos`, los ids sin desglose
determinista, de plantilla o sin todos los criterios core, y no duplica lo
ya registrado. Di en el resumen cuántos escribió y cuántos omitió, con el
número; borra después el desglose de `tmp/`.

```json
{"session_id":"YYYYMMDD-HHMMSS","message_id":"<id>","tier":"REVIEW","score_final":7,"criterios":{"cambia_algo_concreto":1,"sorpresa_bayesiana":0},"veredictos":{"cambia_algo_concreto":"si"},"origen":"vectores","ts_registro":"..."}
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
