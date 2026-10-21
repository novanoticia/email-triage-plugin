<!-- Referencia del PASO 4.I (extraída en v3.21.33 para dar margen al
SKILL.md, que se carga entero en cada activación). El SKILL.md deja la regla
write-ahead y la condición de entrada: antes del primer movimiento real. -->

## PASO 4.I — Registro de sesión (detalle)

### Cuándo registrar

Registrar una entrada por cada correo que se vaya a mover, inmediatamente
antes de ejecutar el `move` (write-ahead: si el proceso muere a mitad del
movimiento, el log conserva el rastro).

### Formato de entrada

```
{"session_id":"YYYYMMDD-HHMMSS","ts":"ISO8601","message_id":"<id>","subject":"...","from":"...","from_folder":"...","to_folder":"...","tier":"REVIEW","score":7,"modo_scoring":"determinista","status":"pending"}
```

Un movimiento sin `score` es **regla manual** y solo si la persona lo pide
(«mueve todo lo de X»): `"origen":"regla_manual","regla":"remitente=…"`,
`tier`/`score` a `null`, y se confirma diciendo que no se puntuó. `registrar`
rechaza cualquier otro movimiento sin `score`.

El log es **append-only (v3.5)**: NUNCA editar líneas ya escritas —
editar líneas concretas de un JSONL es frágil y, si falla a mitad,
corrompe justo el archivo que permite revertir. `status: pending`
significa "movimiento lanzado". Si el `move` FALLA, añadir (append) una
línea de evento e informar al usuario:

```
{"event":"move_failed","session_id":"...","message_id":"<id>","ts":"ISO8601"}
```

Al terminar el SCRIPT 3, **cierra el lote** pegando su return literal (sin
resumirlo): `cerrar-lote` lo parsea y registra cuántos se movieron y cuáles
fallaron. Sin cierre, el PASO 5.V da `sin_cerrar`.

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
`{"ok":false,"error":...}`; si falla, avisa al usuario y continúa el triaje.
Si trae `bloquea_movimiento`, ese correo **no se mueve** (ni por el fallback).
Si trae `aviso_ruta`, la línea se escribió fuera de la base de estado y nadie la
leerá: dilo con la ruta, no muevas más y **no copies las líneas a mano** al log
real; vuelve a registrar en la ruta correcta.

**Fallback**: si no puedes ejecutar Python, usar Desktop Commander (`write_file`)
para añadir la línea a `~/.email-triage/session_log.jsonl` (crear el directorio
con `create_directory` la primera vez). El log es una red de seguridad, no un
requisito para operar; su única regla es que sea **append-only** — con el
helper, además, concurrente-seguro.

### Retención

**Retención (v3.5)**: la purga vive al FINAL del PASO 5 (tras escribir
telemetría), nunca durante un undo — reescribir el log justo cuando se
necesita íntegro para revertir era el peor momento posible. Al cerrar
cada sesión: si el log contiene entradas con `ts` de hace más de 30
días, reescribirlo conservando solo las recientes e informar cuántas se
purgaron. El undo (PASO 6) solo LEE el log, jamás lo reescribe (sus
registros son appends).
