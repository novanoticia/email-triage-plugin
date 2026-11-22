<!-- Referencia del PASO 4.I (extraída en v3.21.33 para dar margen al
SKILL.md, que se carga entero en cada activación). El SKILL.md deja la regla
write-ahead y la condición de entrada: antes del primer movimiento real. -->

## PASO 4.I — Registro de sesión (detalle)

### Cuándo registrar

Registrar una entrada por cada correo autorizado antes de ejecutar el lote
(write-ahead). En Mail.app, incluye el `lote_id` devuelto por `montar-mover`,
`mail_account_id` y el `mail_id` de la instancia confirmada. Usa los buzones
reales para `from_folder` y `to_folder` (`Archive` si se eligió archivo
nativo). Ejecuta solo tras registrar todas las entradas del lote.

### Formato de entrada

```
{"session_id":"YYYYMMDD-HHMMSS","ts":"ISO8601","message_id":"<id>","subject":"...","from":"...","from_folder":"...","to_folder":"...","tier":"REVIEW","score":7,"modo_scoring":"determinista","status":"pending"}
```

Un movimiento sin `score` es **regla manual** y solo si la persona lo pide
(«mueve todo lo de X»): `"origen":"regla_manual","regla":"remitente=…"`,
`tier`/`score` a `null`, y se confirma diciendo que no se puntuó. `registrar`
rechaza cualquier otro movimiento sin `score`.

El log es **append-only**. `status: pending` conserva el intento previsto.
Para los lotes de Mail.app el recibo distingue `confirmado`, `fallido` y
`no_verificado` por instancia. Para el flujo legado sin recibo JSON, un
movimiento fallido se registra así:

```
{"event":"move_failed","session_id":"...","message_id":"<id>","ts":"ISO8601"}
```

Al terminar el SCRIPT 3, **cierra el lote** pasando su salida literal en
`salida`. En Mail.app, `cerrar-lote` coteja el recibo con el registro previo
y lo guarda una sola vez. Informa por separado de las instancias
`no_verificado` antes de cualquier reintento.

```bash
# cerrar-lote.json: {"session_id":"<SID>","salida":"<return del SCRIPT 3>"}
python3 "<ruta-del-skill>/scripts/triage_helpers.py" cerrar-lote < ~/.email-triage/tmp/cerrar-lote.json
```

### Dónde escribir

**Vía canónica (v3.8.2)**: usar el helper `registrar`, que hace un **append
atómico bajo lock de fichero** (`fcntl.flock`). Evita que dos sesiones a la vez
(p. ej. una tarea programada y una manual) entrelacen líneas y corrompan el
JSONL, crea el directorio con permisos `700`/`600` si falta y garantiza una
sola línea por registro:

```bash
# registrar.json:
#   {"session_id":"...","message_id":"<id>","tier":"REVIEW","status":"pending"}
python3 "<ruta-del-skill>/scripts/triage_helpers.py" registrar --ruta ~/.email-triage/session_log.jsonl < ~/.email-triage/tmp/registrar.json
```

El mismo helper sirve para `correcciones.jsonl`. Devuelve `{"ok":true,...}` o
`{"ok":false,"error":...}`. Si falla, avisa al usuario y continúa en modo
propuesta.
Si trae `bloquea_movimiento`, ese correo **no se mueve** (ni por el fallback).
Si trae `aviso_ruta`, la línea se escribió fuera de la base de estado y nadie la
leerá: dilo con la ruta, no muevas más y **no copies las líneas a mano** al log
real; vuelve a registrar en la ruta correcta.

Si no puedes ejecutar el helper de registro, presenta el lote para que la
persona lo aplique manualmente.

La retención del log vive en el SKILL.md (PASO 4.I), porque se aplica al
cerrar cualquier sesión, haya o no movimientos.
