# Errores reales observados en producción (Mail.app/iCloud)

> Extraído del SKILL.md en v3.4 para reducir su tamaño en contexto.
> Leer bajo demanda con Desktop Commander.

## Errores reales observados en producción (v3.0.1)

Documentación de bugs encontrados en sesiones reales con Mail.app/iCloud:

1. **"Buzones de entrada" no es un buzón real** — Es un grupo visual de macOS
   Mail, no un mailbox. El buzón real se llama `INBOX`. Usar siempre los
   nombres reales que devuelve `name of every mailbox of account`.

2. **Índice shifting al mover en bucle** — Mover el mensaje en índice 9 hace
   que el que estaba en 10 pase a 9, el de 11 a 10, etc. Si se procesan
   los índices de menor a mayor, se mueven mensajes incorrectos. La solución
   no es "de mayor a menor" (también falla en sesiones con múltiples lotes),
   sino **capturar referencias a objetos antes de mover** (ver PASO 1).

3. **osascript inline con caracteres UTF-8** — Nombres de carpeta como
   "Leer Después" provocan errores de sintaxis cuando se pasan como
   AppleScript inline al conector osascript. Solución: escribir el script
   a `/tmp/` con Desktop Commander y ejecutar con `start_process`.

4. **`do shell script "osascript /path"` desde osascript** — El patrón de
   anidar osascript dentro de `do shell script` funciona para scripts cortos,
   pero falla silenciosamente con scripts largos o con output extenso.
   Preferir `start_process` + `read_process_output` de Desktop Commander.

5. **Creación de carpetas** — Si `carpetas.destino` no existe, hay que crearla
   explícitamente con `make new mailbox with properties {name:"X"} at acct`.
   Mail.app no la crea implícitamente al mover.

6. **Timeouts en lotes grandes (>100 correos)** — La lectura de metadatos de
   150+ correos puede superar el timeout de osascript. Procesarlos en lotes
   de 25-50 con scripts separados.

---
