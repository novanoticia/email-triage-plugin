<!-- Extraido de SKILL.md v3.8.13 (CM1, auditoria 2026-07-17):
     divulgacion progresiva. Este fichero se lee SOLO cuando la fase
     lo requiere; el nucleo del SKILL.md enruta hasta aqui. -->

## MANEJO DE ERRORES Y RESILIENCIA

Este skill depende de conectores externos (Mail.app vía osascript, Gmail MCP)
que pueden fallar por múltiples razones. El skill DEBE ser resiliente y nunca
dejar al usuario sin feedback.

### Principio general

**Fallar con gracia, informar siempre, degradar sin abortar.**

Si una operación falla, el skill debe:
1. Informar al usuario qué falló y por qué (si se puede determinar)
2. Intentar continuar en modo degradado
3. No dejar la sesión en un estado inconsistente (ej: correos parcialmente movidos)

### Errores de conexión al proveedor

| Error | Causa probable | Acción |
|-------|---------------|--------|
| osascript timeout / no responde | Mail.app cerrado o colgado | Informar: "Mail.app no responde. ¿Está abierto?" y ofrecer reintento |
| Gmail MCP no disponible | Conector no instalado o token expirado | Informar: "No puedo acceder a Gmail. Verifica que el conector Gmail MCP esté activo en Configuración → Conectores" |
| Carpeta no encontrada | Nombre incorrecto en config.yaml | Listar carpetas disponibles y pedir al usuario que elija |
| Permiso denegado (osascript) | macOS bloqueó el acceso | Informar: "macOS necesita permiso para controlar Mail.app. Ve a Ajustes del Sistema → Privacidad → Automatización" |

### Retry con backoff para operaciones de lectura

Cuando una llamada al conector falla (lectura de correos o de cuerpo):

1. **Primer intento**: ejecutar normalmente
2. **Si falla**: esperar 2 segundos, reintentar
3. **Si falla de nuevo**: esperar 5 segundos, reintentar una última vez
4. **Si falla 3 veces**: informar al usuario y continuar sin esa operación

**No aplicar retry a operaciones de escritura/mover** — el riesgo de duplicación
es peor que fallar. Si mover un correo falla, informar y pasar al siguiente.

### Protección contra emails enormes

El control de volumen tiene exactamente DOS números de CARACTERES (v3.5)
más UN límite de LÍNEAS que aplica el modelo (QW3/F5, auditoría 2026-07-17):

1. **Extracción cruda: 4000 caracteres** (PASO 1) — generosa a propósito,
   porque la limpieza viene después y limpiar reduce. Truncar en corto
   antes de sanitizar destruía los correos HTML.
2. **Presupuesto final: `puntuacion.max_caracteres_cuerpo`** (config,
   1500 por defecto) — lo aplica el sanitizador vía `--max-chars` SOBRE
   el texto YA limpio, añadiendo `[truncado]` si recorta.

3. **Límite de líneas: `puntuacion.max_lineas_cuerpo`** (config, 30 por
   defecto; 20 en veloz) — lo aplica el MODELO sobre el cuerpo ya
   sanitizado; no pasa por el script.

No existe ningún otro límite de caracteres o líneas; si aparecen números
distintos (500/2000) en docs o logs antiguos, son de versiones anteriores
a v3.5.

Fuente parseable: ambos números de caracteres viven como claves en la
plantilla `config.yaml` (`puntuacion.extraccion_cruda_max` y
`puntuacion.perfiles`); el gate `ContratoDoctrinaConstantesR2` de
`test_contrato_skill.py` compara cada cita numérica de esta doctrina y de
los scripts con esas claves.

**Reglas de lote (sin cambios):**
- Si el lote total supera 30 correos con cuerpo, procesar en sublotes de 15
  para evitar saturar la ventana de contexto
- **Nunca cargar adjuntos** — el skill opera solo sobre metadatos y texto

### Timeout y feedback al usuario

Si una operación tarda más de lo esperado:

- **Lectura de buzón (>30 correos)**: informar al usuario cada 10 correos
  procesados con un mensaje breve: "Procesados 10/45..."
- **Análisis epistémico**: si el lote es grande (>20), avisar al inicio:
  "Analizando N correos, esto puede tardar un momento"
- **Mover correos en lote**: confirmar cada movimiento exitoso si el modo
  es `confirmacion`; en modo `lote` o `silencioso`, informar al final con
  el conteo de éxitos y fallos

### Validación de contenido HTML, Base64 y basura

**Esta sección queda cubierta por el PASO 1.B — Sanitización del cuerpo.**

El pipeline completo de sanitización (strip reply chains → strip HTML → detectar
Base64 → eliminar firmas → validación final) se aplica SIEMPRE antes de que el
cuerpo llegue al motor epistémico. Ver PASO 1.B para el procedimiento detallado
y la tabla de etiquetas de estado del cuerpo.

**Regla cardinal**: nunca evaluar criterios epistémicos sobre texto que no haya
pasado por el pipeline S1-S5. HTML en bruto, CSS, Base64, firmas corporativas y
reply chains son basura para el motor de inferencia y generan falsos positivos.

### Modo degradado

Si el skill no puede acceder al cuerpo del correo (fallo de `content` en
Mail.app, o imposibilidad de llamar a `gmail_read_message`):

1. **No abortar** — continuar con asunto + remitente + fecha
2. Marcar los correos afectados con `[solo metadatos]` en la explicación
3. Aplicar solo los criterios evaluables sin cuerpo: hard rules, criterios
   1-5 (Grupo A + Grupo B), y criterio 28 (entangled truths por metadatos)
4. Advertir al usuario: "N correos analizados sin acceso al cuerpo.
   La precisión del triaje puede ser menor para estos."

### Validación de config.yaml al inicio

Antes de ejecutar cualquier fase, validar:

1. `usuario.nombre` no está vacío → si lo está, pedir al usuario
2. `usuario.perfil` contiene al menos 10 caracteres → si no, advertir
   que el triaje será genérico
3. `correo.proveedor` es uno de: "icloud", "gmail", "otro" → si no, preguntar
4. `correo.cuenta` no está vacía → si lo está, pedir al usuario
5. `carpetas.entrada` y `carpetas.pendiente` no están vacías → si lo están,
   usar "INBOX" y "Leer Después" como fallback e informar
6. `tiers` tiene los 4 valores → si falta alguno, usar defaults
   (reply_needed: 10, review: 4, reading_later: 0, archive: -1)
7. `carpetas.destino` existe en el cliente de correo → si no, crearla
   explícitamente (Mail.app: `make new mailbox with properties {name:"X"} at acct`;
   no se crea implícitamente al mover)

Si faltan campos críticos (nombre, cuenta, proveedor), no continuar hasta
que el usuario los proporcione. Presentar un setup guiado breve.

---

