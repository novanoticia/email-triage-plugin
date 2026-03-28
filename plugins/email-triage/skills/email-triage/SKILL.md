---
name: email-triage
description: >
  Triaje inteligente de correo electrónico: analiza bandejas de entrada y carpetas
  de lectura pendiente para identificar correos de alto valor usando un criterio
  de "valor diferencial" (¿leer esto cambiaría algo concreto para el usuario?).
  Soporta iCloud (Mail.app vía AppleScript), Gmail (vía MCP) y cualquier cliente
  compatible con Cowork. Incluye calibración estadística basada en historial y
  sistema de puntuación ponderada por categoría.
  Actívalo cuando el usuario diga "filtra mi correo", "revisa mi bandeja",
  "triaje de emails", "qué correos son importantes", "email triage",
  "clasifica mis correos", "qué debería leer", "hay algo urgente en mi correo",
  "revisa Leer Después", "filtra newsletters", o cualquier petición que implique
  evaluar, priorizar o clasificar correos electrónicos.
  También se activa si el usuario pide mover correos entre carpetas basándose
  en relevancia o importancia.
---

# Email Triage v2.0 — Filtrado inteligente por valor diferencial

## Qué hace este skill

Evalúa correos electrónicos usando un criterio epistémico: no "¿es importante?"
sino **"¿leer esto cambiaría algo concreto para el usuario?"**.

Opera en fases modulares (calibración, urgentes, triaje profundo) y se adapta
a cualquier perfil profesional y proveedor de correo.

### Cambios en v2.0

- **Acceso al cuerpo del email** — lectura de contenido real, no solo asunto
- **Puntuación ponderada** — pesos configurables por keyword y categoría
- **Calibración estadística real** — extracción de patrones con frecuencias
- **Lotes optimizados** — procesamiento de hasta 50 correos por lote

---

## PASO 0 — Leer configuración

Lee `config.yaml` antes de cualquier fase. Contiene perfil, carpetas y pesos.

Si no existe, pide al usuario estos campos mínimos:
1. **nombre** y **perfil** (rol, formación, intereses)
2. **proyectos_activos**
3. **proveedor** de correo y **carpetas**
4. **modo** de interacción

Sin perfil, el criterio de valor diferencial no tiene ancla.

---

## PASO 1 — Conectar al proveedor de correo

### iCloud / Mail.app (macOS)

Usa "Control your Mac" (osascript) para acceder a Mail.app.

#### Listar correos con metadatos y extracto del cuerpo

```applescript
tell application "Mail"
    set acct to account "NOMBRE_CUENTA"
    set targetMailbox to mailbox "NOMBRE_CARPETA" of acct
    set msgs to messages of targetMailbox
    set msgCount to count of msgs

    -- Procesar en lote (hasta 50 por ejecución)
    set batchSize to 50
    if msgCount < batchSize then set batchSize to msgCount

    set resultList to {}
    repeat with i from 1 to batchSize
        set msg to item i of msgs
        set msgSubject to subject of msg
        set msgSender to sender of msg
        set msgDate to date received of msg

        -- ACCESO AL CUERPO: extraer primeras líneas del contenido
        try
            set msgContent to content of msg
            -- Truncar a primeros 500 caracteres para eficiencia
            if length of msgContent > 500 then
                set msgContent to text 1 thru 500 of msgContent
            end if
        on error
            set msgContent to "(sin acceso al cuerpo)"
        end try

        set end of resultList to "---EMAIL " & i & "---" & ¬
            linefeed & "Asunto: " & msgSubject & ¬
            linefeed & "De: " & msgSender & ¬
            linefeed & "Fecha: " & (msgDate as string) & ¬
            linefeed & "Extracto: " & msgContent
    end repeat

    -- Devolver como texto concatenado
    set AppleScript's text item delimiters to linefeed & linefeed
    set output to resultList as string
    set AppleScript's text item delimiters to ""
    return output
end tell
```

**Nota sobre `content` de Mail.app**: La propiedad `content` devuelve el texto
plano del correo. Si el correo es solo HTML sin parte text/plain, puede devolver
el HTML en bruto. En ese caso, el modelo debe extraer el texto relevante
ignorando las etiquetas HTML. Si `content` falla (error de permisos o formato),
el bloque `try/on error` asegura que el triaje continúa solo con asunto y remitente.

#### Mover un correo

```applescript
tell application "Mail"
    set acct to account "NOMBRE_CUENTA"
    set destMailbox to mailbox "CARPETA_DESTINO" of acct
    set sourceMailbox to mailbox "CARPETA_ORIGEN" of acct
    set msgs to messages of sourceMailbox

    -- Mover por índice (o por message id si se guardó)
    move message i of sourceMailbox to destMailbox
end tell
```

#### Mover múltiples correos por índice (lote)

```applescript
tell application "Mail"
    set acct to account "NOMBRE_CUENTA"
    set sourceMailbox to mailbox "CARPETA_ORIGEN" of acct
    set destMailbox to mailbox "CARPETA_DESTINO" of acct

    -- Lista de índices a mover (de mayor a menor para no alterar posiciones)
    set indicesToMove to {45, 32, 18, 7, 3}
    repeat with idx in indicesToMove
        move message idx of sourceMailbox to destMailbox
    end repeat
end tell
```

**IMPORTANTE**: Al mover en lote, procesar los índices de mayor a menor.
Mover un mensaje altera los índices posteriores si se procesan de menor a mayor.

### Gmail (vía MCP)

Flujo verificado con herramientas Gmail MCP:

1. **Listar** con `gmail_search_messages` — query Gmail estándar, paginación
   con `nextPageToken`, `maxResults` hasta 500
2. **Leer cuerpo** con `gmail_read_message` — solo para correos que pasan
   el filtro inicial por snippet/asunto (evita sobrecargar la sesión)
3. **Mover** entre etiquetas — añadir destino, eliminar origen

### Otro proveedor

Preguntar al usuario qué conectores MCP o AppleScript tiene disponibles.

---

## PASO 2 — CALIBRACIÓN ESTADÍSTICA

La calibración extrae patrones reales del historial del usuario. No es una
descripción conceptual: es un análisis cuantitativo que produce datos usables.

### Procedimiento concreto

1. Accede a `carpetas.historial` (por defecto "Conservar").

2. Lee los últimos 100 correos con asunto, remitente y fecha.

3. **Extrae estas métricas exactas**:

   **a) Remitentes frecuentes** (top 10 por apariciones):
   ```
   remitente@ejemplo.com — 12 correos (12%)
   otro@dominio.org — 8 correos (8%)
   ...
   ```

   **b) Dominios de remitente frecuentes** (top 5):
   ```
   @substack.com — 23 correos
   @gmail.com — 18 correos
   ...
   ```

   **c) Palabras clave en asuntos** (top 15, excluyendo stopwords):
   ```
   "AI" — 14 apariciones
   "update" — 11 apariciones
   ...
   ```

   **d) Distribución temporal**:
   ```
   Correos más antiguos: DD/MM/YYYY
   Correos más recientes: DD/MM/YYYY
   Pico de conservación: [mañana/tarde/noche]
   ```

   **e) Tipos detectados**:
   ```
   Newsletters: ~45%
   Comunicaciones directas: ~30%
   Notificaciones de servicio: ~15%
   Otros: ~10%
   ```

4. **Almacena el perfil** como contexto interno para las fases siguientes.
   Úsalo para:
   - Dar +2 puntos a remitentes que aparecen 5+ veces en historial
   - Dar +1 punto a dominios frecuentes
   - Dar +1 punto a correos cuyo asunto contiene keywords del top 15

5. Si `mostrar_calibracion: true`, presenta las métricas al usuario.
   Si no, solo confirma: "Calibración lista: X correos analizados, Y remitentes
   frecuentes, Z keywords identificadas."

### Cuándo recalibrar

- A petición del usuario
- Si más de 3 "No" consecutivos en modo confirmación
- Si la carpeta de historial ha cambiado significativamente (>50 correos nuevos)

### Calidad de la calibración

Si la carpeta tiene contenido muy heterogéneo, informa y sugiere acotar
por rango de fechas o excluir ciertos dominios del análisis.

---

## PASO 3 — BANDEJA DE ENTRADA (urgentes)

Revisa `carpetas.entrada` (últimas 48-72 horas).

### Criterio de urgencia

Urgente = AMBAS condiciones:
1. Ventana temporal corta (deadline, evento, expiración)
2. Relevante para el perfil del usuario

### Formato

```
📬 [Asunto]
   De: [Remitente]
📝 Resumen: [2-3 líneas del contenido]
⚡ Por qué ahora: [ventana temporal]
🔵 Recomendación: LEER AHORA / PUEDE ESPERAR
```

Según modo: espera confirmación, presenta en lote, o actúa directamente.

Si no hay urgentes: "Nada en la bandeja requiere atención inmediata."

---

## PASO 4 — TRIAJE PROFUNDO (puntuación ponderada)

Esta es la fase principal. Revisa `carpetas.pendiente`.

### Sistema de puntuación

Cada correo recibe una puntuación numérica. El umbral para MOVER es
configurable en `config.yaml` (por defecto: **3 puntos**).

#### Fuentes de puntuación

| Fuente | Puntos | Condición |
|--------|--------|-----------|
| **Remitente prioritario** | +3 | Está en `remitentes_prioritarios` |
| **Remitente en historial** (5+ veces) | +2 | Detectado en calibración |
| **Dominio en historial** | +1 | Dominio frecuente en calibración |
| **Keyword boost (alta)** | +3 | Palabra en `palabras_clave_boost` con peso `alto` |
| **Keyword boost (media)** | +2 | Palabra en `palabras_clave_boost` con peso `medio` |
| **Keyword boost (baja)** | +1 | Palabra en `palabras_clave_boost` con peso `bajo` o sin peso |
| **Keyword en cuerpo** | +1 | Keyword encontrada en extracto del cuerpo (no solo asunto) |
| **Keyword penalizar** | -2 | Palabra en `palabras_clave_penalizar` |
| **Remitente ignorar** | -99 | Está en `remitentes_ignorar` (skip total) |
| **Criterio valor diferencial** | +2 | El modelo determina que cumple uno de los 5 criterios (ver abajo) |

#### Los 5 criterios de valor diferencial

Evalúa en orden. Si alguno aplica, suma +2 al score y asigna categoría:

1. **ACCIÓN** — ¿Requiere acción con fecha límite real?
2. **OPERATIVO** — ¿Modifica una decisión o plan activo del usuario?
3. **ESTRATÉGICO** — ¿Contiene conocimiento técnico/conceptual aplicable?
4. **HERRAMIENTAS** — ¿Afecta a herramientas o plataformas que usa?
5. **VENTAJA** — ¿Ofrece perspectiva que daría ventaja real al usuario?

#### Señales de DEJAR (no mover)

- Información recuperable con una búsqueda web
- Confirmaciones, recibos o notificaciones sin acción
- Eco de algo que el usuario ya conoce
- Valor que caduca antes de que el usuario pueda actuar
- Newsletter genérica sin contenido aplicable

### Evaluación con acceso al cuerpo

Cuando se dispone del extracto del cuerpo (propiedad `content` de Mail.app
o `body` de Gmail MCP), el skill debe:

1. **Primer filtro rápido** — Evaluar asunto + remitente (puntuación parcial)
2. **Si score parcial >= 1** — Analizar también el extracto del cuerpo:
   - Buscar keywords de boost/penalización en el texto
   - Evaluar criterios de valor diferencial con contexto completo
3. **Si score parcial < 1 y remitente no está en ignorar** — Leer el extracto
   igualmente, pero con umbral más exigente (el cuerpo debe aportar >= 2 puntos
   para alcanzar el umbral de MOVER)

Este enfoque en dos pasadas evita procesar en profundidad correos que
claramente no son relevantes, pero no descarta correos con asuntos vagos
que podrían tener contenido valioso.

### Formato de presentación

```
📧 [Asunto]
   De: [Remitente] | Fecha: [DD/MM]
📝 Resumen: [2-3 líneas del contenido real]
📊 Puntuación: X/umbral (desglose: remitente +N, keywords +N, criterio +N)
🏷️ Categoría: [ACCIÓN | OPERATIVO | ESTRATÉGICO | HERRAMIENTAS | VENTAJA]
🔵 Recomendación: MOVER / DEJAR
```

### Control de flujo según modo

**Modo `confirmacion`** (por defecto):
- Un correo a la vez, espera Sí/No antes de mover

**Modo `lote`**:
- Presenta todos con recomendaciones, pide confirmación global
- "¿Muevo los marcados? Puedes excluir por número"

**Modo `silencioso`**:
- Mueve automáticamente los que superan el umbral
- Presenta resumen al final con desglose

### Gestión de escala

- **Lote estándar**: hasta 50 correos por ejecución (configurable con `limite_por_sesion`)
- Si hay más de 50: informar volumen, procesar por lotes, priorizar recientes
- **Índices en orden descendente** al mover para no alterar posiciones
- Si la carpeta tiene >200 correos: sugerir un primer pase rápido solo por
  remitente/asunto (sin leer cuerpos) para descartar el ruido evidente,
  seguido de un segundo pase con lectura de cuerpo para los supervivientes

---

## PASO 5 — RESUMEN DE SESIÓN

```
───────────────────────────────────
RESUMEN DE TRIAJE
───────────────────────────────────
📥 Bandeja de entrada: X correos revisados
   → Y urgentes identificados

📂 [Carpeta pendiente]: X correos revisados
   → Y movidos a [carpeta destino]
   → Z dejados en su sitio

Categorías de lo movido:
   ACCIÓN: N | OPERATIVO: N | ESTRATÉGICO: N
   HERRAMIENTAS: N | VENTAJA: N

📊 Estadísticas de puntuación:
   Puntuación media: X.X | Máxima: X | Mínima: X
   Correos sobre umbral: N (X%)
───────────────────────────────────
```

---

## Errores comunes a evitar

- No asumas que "urgente" en el asunto = urgente real (clickbait de newsletters)
- No muevas sin confirmación en modo `confirmacion`
- Si no puedes acceder a una carpeta, informa y pide verificar el nombre
- No confundas "interesante" con "valioso" — el criterio es impacto, no curiosidad
- Si `content` devuelve HTML crudo, extrae el texto ignorando tags
- Si `content` falla, continúa el triaje solo con asunto/remitente (modo degradado)
- Al mover en lote, procesa índices de mayor a menor
- Si la calibración da un perfil incoherente, informa y sugiere acotar

---

## Dependencias

| Proveedor | Conector necesario | Notas |
|-----------|-------------------|-------|
| iCloud    | Control your Mac (osascript) | Mail.app con cuenta configurada |
| Gmail     | Gmail MCP | Conector en Claude/Cowork |
| Otro      | Según disponibilidad | El skill preguntará |

---

## Personalización (ver config.yaml)

- `remitentes_prioritarios` — umbral bajo (+3)
- `remitentes_ignorar` — skip total (-99)
- `palabras_clave_boost` — con peso: `alto` (+3), `medio` (+2), `bajo` (+1)
- `palabras_clave_penalizar` — reducen puntuación (-2)
- `umbral_mover` — puntuación mínima para recomendar MOVER (default: 3)
- `limite_por_sesion` — máximo por ejecución (default: 50)
- `leer_cuerpo` — `true`/`false`, activa lectura del contenido del email
