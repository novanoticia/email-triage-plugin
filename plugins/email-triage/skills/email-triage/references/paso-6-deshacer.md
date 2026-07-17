<!-- Extraido de SKILL.md v3.8.13 (CM1, auditoria 2026-07-17):
     divulgacion progresiva. Este fichero se lee SOLO cuando la fase
     lo requiere; el nucleo del SKILL.md enruta hasta aqui. -->

## PASO 6 — DESHACER ÚLTIMA SESIÓN

Se activa cuando el usuario dice "deshaz el triaje", "undo", "revierte los movimientos",
"vuelve a como estaba", o similar.

### Procedimiento

1. **Leer el log**: acceder a `~/.email-triage/session_log.jsonl` con Desktop Commander.
   Si no existe o está vacío, informar: "No hay sesiones anteriores registradas."

2. **Identificar la última sesión**: agrupar las entradas por `session_id` y mostrar
   las 3 más recientes para que el usuario elija cuál deshacer:

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

4. **Ejecutar el undo**: para cada entrada de movimiento de la sesión con
   `status: pending` o `moved` (logs de versiones previas) que NO tenga un
   evento `move_failed` ni `undone` posterior con su `message_id`, mover el
   correo de `to_folder` de vuelta a `from_folder` usando el patrón de
   referencias seguro del PASO 1. Si el correo no está en `to_folder` (el
   move original falló sin registrarse, o alguien lo movió a mano), el
   `move` fallará limpiamente y cae en el punto 5.

5. **Resultado parcial**: si algún correo no puede revertirse (ya fue movido
   a otra carpeta manualmente, eliminado, etc.), informar cuáles fallaron y
   añadir (append) por cada uno:
   `{"event":"undo_failed","session_id":"...","message_id":"<id>","ts":"ISO8601"}`.
   No abortar — revertir los que sí se pueda.

6. **Registrar el resultado (append-only)**: por cada correo revertido con
   éxito, añadir
   `{"event":"undone","session_id":"...","message_id":"<id>","undone_at":"ISO8601"}`.
   Una sesión cuyos movimientos tienen todos un evento `undone` deja de
   ofrecerse en el listado del punto 2.

### Qué NO hace el undo

- No revierte cambios de tier ni overrides manuales del usuario
- No recupera correos eliminados permanentemente
- No puede deshacer sesiones sin registro (anteriores a esta versión del plugin)

---

