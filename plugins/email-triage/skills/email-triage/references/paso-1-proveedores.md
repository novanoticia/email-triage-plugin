<!-- Extraido de SKILL.md v3.8.13 (CM1, auditoria 2026-07-17):
     divulgacion progresiva. Este fichero se lee SOLO cuando la fase
     lo requiere; el nucleo del SKILL.md enruta hasta aqui. -->

## PASO 1 — Conectar al proveedor de correo

### iCloud / Mail.app (macOS)

Usa exclusivamente `scripts/leer_mailapp.py` desde un host Python local con
permiso de Automatización para Mail.app. El programa recibe JSON por stdin,
captura la respuesta de AppleScript en un pipe privado y devuelve los
metadatos y el cuerpo después de S0–S5. El cuerpo crudo (≤4000 caracteres)
solo vive en memoria durante la captura.

1. **Metadatos.** Prepara el JSON en un directorio privado y exclusivo de
   esta ejecución (por ejemplo, el que devuelve `mktemp -d`). Usa la cuenta
   y el buzón configurados. `operacion` toma el valor `metadatos` por defecto.
   La entrada admite `limite` y `ventana_horas` opcional. Conserva
   `mail_account_id` y los pares `mail_id` + `message_id` de las filas saneadas.

   ```bash
   # SOLICITUD_MAIL apunta al JSON privado de esta ejecución.
   # Ejemplo de contenido: {"cuenta":"iCloud","origen":"INBOX","limite":50}.
   python3 "<ruta-del-skill>/scripts/leer_mailapp.py" < "$SOLICITUD_MAIL"
   ```

2. **Cuerpos.** Usa el mismo comando con `operacion: "cuerpos"`, la misma
   cuenta y buzón, el `mail_account_id` previo y `correos` con los pares
   seleccionados. Pasa `max_chars` desde
   `puntuacion.max_caracteres_cuerpo` y `sublote` desde
   `resiliencia.sublote_con_cuerpo`. Conserva los campos de seguridad de la
   fila devuelta junto con el extracto. Si un `message_id` es nulo, limita la
   evaluación a metadatos y excluye el correo de los movimientos.

3. **Identidad y reintentos.** Usa `mail_id` y `message_id` conjuntamente
   para asociar el resultado del cuerpo con su fila. Si aparece en
   `mail_ids_no_disponibles`, descarta esa asociación y excluye el mensaje de
   movimientos. Lee `references/paso-1-doctrina-ejecucion.md` para reintentos
   y ejecución en segundo plano.

Un fallo del lector o la falta de permiso detiene la captura afectada. Explica el
fallo y conserva únicamente resultados saneados y de identidad verificada.
El AppleScript interno, las lecturas en línea, el SCRIPT 1 de la plantilla
histórica, `montar-leer-metadatos` y `montar-leer-cuerpos` quedan fuera del
flujo de triaje. Ejecutarlos directamente puede exponer datos crudos.

#### Mover correo con Mail.app

Primero confirma el lote concreto con la persona o con la autorización de
rutina del cliente. Necesitas identificar la cuenta, el buzón de origen, el
destino de cada mensaje y los pares `message_id`/`mail_id` de la lectura.
Una sesión de simulación usa herramientas de solo lectura. Si el cliente
no puede reservar el permiso de escritura a una acción autorizada, ofrece
la propuesta para aplicarla manualmente en Mail.app.

Para un lote autorizado, utiliza `triage_helpers.py montar-mover`. Construye
el JSON con tu herramienta de ficheros y pásalo por stdin:

```bash
# montar-mover.json:
#   {"cuenta":"<cuenta>","mail_account_id":"<id de cuenta de la lectura>",
#   "origen":"<origen>","destino_review":"<destino>",
#   "destino_archive":"<carpeta o vacío para Archive>",
#   "mids_review":["<mid1>"],"mids_archive":["<mid2>"],
#   "instancias_mail":{"<mid1>":1234,"<mid2>":5678}}
python3 "<ruta-del-skill>/scripts/triage_helpers.py" montar-mover < ~/.email-triage/tmp/montar-mover.json
```

Usa el `lote_id` devuelto para registrar cada movimiento antes de ejecutar
con PASO 4.I. Si falta un `mail_id`, falla el registro o cambia la cuenta,
detén el lote. Si `sospechosos` no está vacío, consígnalo en el resumen.
Guarda `script` con la herramienta de ficheros. Ejecuta ese fichero con
`osascript` y tramita el recibo JSON con `cerrar-lote`.

`destino_review` es obligatorio. `destino_archive` vacío resuelve el buzón
`Archive` de la cuenta. Si el buzón se llama de otra forma, configura su
nombre real. `destino_reply_needed` y `mids_reply_needed` solo se usan si
el destino de respuesta difiere del origen.

El script exige una coincidencia única en origen y verifica que coincide
con `mail_id`. Tras moverla, comprueba que esa instancia ya no está en origen
y sí está en destino. Si el recibo dice `no_verificado`, revisa ambos buzones
antes de reintentar o incluir el mensaje en el resumen de éxitos. Cuando
falte el helper, presenta la propuesta para ejecutarla en Mail.app.

#### Caracteres especiales en nombres de carpeta (bug conocido)

⚠️ Los nombres de carpeta con acentos u otros caracteres no-ASCII
(ej: "Leer Después", "Correo sí deseado") **fallan** cuando se pasan
como AppleScript inline al conector osascript.

⚠️ Aparte del problema de codificación, un nombre de carpeta o cuenta con una
**comilla doble** (`Correo "importante"`) rompe el literal AppleScript aunque lo
ejecutes desde fichero: escápalo SIEMPRE con `escapar-applescript` (campo
`escapados`) en los scripts de solo lectura. Para mover, el propio
`montar-mover` escapa esos valores.

**Solución verificada**: escribir el script completo a un fichero temporal
usando Desktop Commander (`write_file` a `/tmp/`) y ejecutarlo con
`do shell script "osascript /tmp/nombre.scpt"`, o alternativamente
buscar la carpeta por iteración:

```applescript
tell application "Mail"
    set acct to account "NOMBRE_CUENTA"
    set allBoxes to every mailbox of acct
    set targetBox to missing value
    repeat with mb in allBoxes
        if name of mb is "Leer Después" then
            set targetBox to mb
            exit repeat
        end if
    end repeat
    -- targetBox ya es una referencia válida
end tell
```

Cuando se usa `start_process` de Desktop Commander, el fichero `.scpt`
se escribe correctamente en UTF-8 y osascript lo interpreta sin problemas.
Este patrón es más robusto que el acceso inline.

### Gmail (vía MCP)

Se requiere un conector que ejecute S0–S5 **antes** de entregar al agente
asuntos, remitentes, snippets y cuerpos. Las llamadas directas a
`gmail_search_messages` y `gmail_read_message` pueden devolver texto crudo al
contexto. El plugin carece de un adaptador Gmail operativo que intercepte y
sanee esas respuestas. Detén la captura si el host solo ofrece esas llamadas.
Un mensaje mostrado al agente antes de S0–S5 queda fuera de la garantía,
aunque se sanee después o una persona revise la propuesta.

### Otro proveedor

Usa solo una vía de acceso que sanee los datos de correo antes de entregar
cualquier resultado al agente. Si no consta esa garantía, detén la captura
y explica la limitación del proveedor.

---
