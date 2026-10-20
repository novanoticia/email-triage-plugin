<!-- Extraido de SKILL.md v3.8.13 (CM1, auditoria 2026-07-17):
     divulgacion progresiva. Este fichero se lee SOLO cuando la fase
     lo requiere; el nucleo del SKILL.md enruta hasta aqui. -->

## PASO 6 — DESHACER ÚLTIMA SESIÓN

Se activa cuando el usuario dice "deshaz el triaje", "undo", "revierte los movimientos",
"vuelve a como estaba", o similar.

### Procedimiento

1. **Leer el log** (v3.21.13: con el script, no a mano):
   `python3 <scripts>/triage_helpers.py estado-log` lista las 3 sesiones más
   recientes con algo que deshacer (`--ultimas N` para más). Solo lee; no
   agrupes el JSONL tú. Si `sesiones` viene vacía y no hay log, informar:
   "No hay sesiones anteriores registradas." Si hay log pero todo está ya
   deshecho o fallido, dilo así (es lo que explica su `aviso`).

2. **Identificar la última sesión**: muestra las de `sesiones` (ya vienen
   agrupadas, la más reciente primero, con `deshacibles`) para que el usuario
   elija cuál deshacer. Las de `sesiones_sin_confirmar` NO se ofrecen: no
   consta que sus correos se movieran. Dilo con el número y según su
   `cierre`: `sin_cerrar` = nunca se cerró el lote (`cerrar-lote`);
   `descuadre` = hay cierre pero sus cuentas no cuadran con lo registrado.
   Solo si la persona pide expresamente deshacerla, avisa de que puede
   fallar en todos y repite el punto 4 con `--incluir-sin-cerrar`.
   La antigüedad («hace 2 horas») sale de `antiguedad` (cantidad y unidad,
   calculadas por el script con su sello UTC): redáctala, no la calcules.
   Si `antiguedad` es null (sesión anterior a v3.21.15), da la fecha del
   `session_id` sin inventar cuánto hace:

   ```
   Sesiones disponibles para deshacer:
   1. 20250407-143022 — 12 correos movidos (hace 2 horas)
   2. 20250406-091500 — 8 correos movidos (ayer)
   3. 20250405-162300 — 23 correos movidos (hace 2 días)
   ¿Cuál quieres deshacer? (1/2/3 o "cancelar")
   ```

3. **Confirmar siempre**, incluso en modo `silencioso`:
   ```
   Voy a revertir N correos: [lista de asuntos].
   ¿Confirmas? (sí/no)
   ```

4. **Ejecutar el undo**: `estado-log --session <id>` devuelve cada correo con
   su `estado` y `deshacible`; revierte SOLO los que traen `deshacible: true`
   (el script ya aplica esta regla; el `subject` ya pasó por S0 y, si trae
   `injection_subject`, viene vacío: identifica ese correo por tier y carpeta,
   nunca leyendo el log a mano) — para cada entrada de movimiento de la sesión con
   `status: pending` o `moved` (logs de versiones previas) que NO tenga un
   evento `move_failed` ni `undone` posterior con su `message_id` (ni figure
   en los `fallidos` de su `move_batch_done`, desde v3.21.4), mover el
   correo de `to_folder` de vuelta a `from_folder` usando el patrón de
   referencias seguro del PASO 1. Si el correo no está en `to_folder` (el
   move original falló sin registrarse, o alguien lo movió a mano), el
   `move` fallará limpiamente y cae en el punto 5.

5. **Resultado parcial**: si algún correo no puede revertirse (ya fue movido
   a otra carpeta manualmente, eliminado, etc.), informar cuáles fallaron.
   No abortar — revertir los que sí se pueda.

6. **Registrar el resultado** (v3.21.18: con el script, no a mano). Al
   terminar, una sola llamada con los message_id tal como los dio
   `estado-log --session`:

   ```bash
   python3 <scripts>/triage_helpers.py cerrar-deshacer --datos \
     '{"session_id":"<id>","revertidos":["<id1>",...],"fallidos":["<id2>",...]}'
   ```

   Añade `"incluir_sin_cerrar": true` solo si el punto 2 lo usó. El script
   comprueba que cada correo es de esa sesión y deshacible; si uno no lo es
   (`ajenos`, `no_deshacibles`) no escribe nada: dilo con su número, no lo
   corrijas a mano. Los que otro deshacer ya devolvió se omiten
   (`ya_deshechos`, sin error). `registrar` rechaza `undone`/`undo_failed` escritos a
   mano. Una sesión sin correos deshacibles deja de ofrecerse en el punto 2.

### Qué NO hace el undo

- No revierte cambios de tier ni overrides manuales del usuario
- No recupera correos eliminados permanentemente
- No puede deshacer sesiones sin registro (anteriores a esta versión del plugin)

---

