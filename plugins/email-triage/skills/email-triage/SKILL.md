---
name: email-triage
description: >
  Triaje inteligente de correo electrónico: analiza bandejas de entrada y carpetas
  de lectura pendiente para identificar correos de alto valor usando criterios
  epistémicos inspirados en racionalidad bayesiana (LessWrong Sequences).
  No pregunta "¿es importante?" sino "¿leer esto cambiaría algo concreto para
  el usuario?" y evalúa calidad evidencial, riesgo de manipulación, coste
  cognitivo y necesidad de acción.
  Soporta iCloud (Mail.app vía AppleScript), Gmail (vía MCP) y cualquier cliente
  compatible con Cowork. Incluye calibración estadística basada en historial,
  scoring multi-eje con 30 criterios epistémicos, routing por 4 tiers
  (reply_needed, review, reading_later, archive) y explicación de cada decisión.
  Actívalo cuando el usuario diga "filtra mi correo", "revisa mi bandeja",
  "triaje de emails", "qué correos son importantes", "email triage",
  "clasifica mis correos", "qué debería leer", "hay algo urgente en mi correo",
  "revisa Leer Después", "filtra newsletters", o cualquier petición que implique
  evaluar, priorizar o clasificar correos electrónicos.
  También se activa si el usuario pide mover correos entre carpetas basándose
  en relevancia o importancia.
---

# Email Triage v3.0 — Filtrado epistémico por valor diferencial

## Qué hace este skill

Evalúa correos electrónicos usando un marco epistémico multi-eje inspirado en
racionalidad bayesiana. No "¿es importante?" sino **"¿leer esto cambiaría algo
concreto para el usuario?"**, combinado con análisis de calidad evidencial,
detección de manipulación/ruido, coste cognitivo y urgencia real.

Opera en fases modulares (calibración, urgentes, triaje profundo) y se adapta
a cualquier perfil profesional y proveedor de correo.

### Cambios en v3.0

- **30 criterios epistémicos** — inspirados en LessWrong Sequences (Value of
  Information, Bayesian Surprise, Filtered Evidence, Forward/Backward Flow, etc.)
- **Scoring multi-eje** — 5 subejes: valor decisional, calidad epistémica,
  riesgo de manipulación, coste cognitivo, presión de acción
- **4 tiers de routing** — reply_needed, review, reading_later, archive
  (en lugar del binario MOVER/DEJAR)
- **Explicación por correo** — top 3 razones positivas y negativas
- **Telemetría y aprendizaje** — registro de decisiones y correcciones del usuario
- **Compatible con v2.0** — mantiene acceso al cuerpo, calibración estadística,
  puntuación por keywords y lotes optimizados

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

## PASO 4 — TRIAJE PROFUNDO (scoring epistémico multi-eje)

Esta es la fase principal. Revisa `carpetas.pendiente`.

### 4.A — Reglas duras (hard rules)

Antes de evaluar criterios epistémicos, aplica reglas deterministas:

| Fuente | Puntos | Condición |
|--------|--------|-----------|
| **Remitente prioritario** | +3 | Está en `remitentes_prioritarios` |
| **Remitente en historial** (5+ veces) | +2 | Detectado en calibración |
| **Dominio en historial** | +1 | Dominio frecuente en calibración |
| **Keyword boost (alta)** | +3 | Palabra con peso `alto` |
| **Keyword boost (media)** | +2 | Palabra con peso `medio` |
| **Keyword boost (baja)** | +1 | Palabra con peso `bajo` o sin peso |
| **Keyword en cuerpo** | +1 | Keyword en extracto del cuerpo |
| **Keyword penalizar** | -2 | Palabra en `palabras_clave_penalizar` |
| **Remitente ignorar** | -99 | Está en `remitentes_ignorar` (skip total) |
| **Pregunta directa al usuario** | +4 | El correo hace una pregunta directa |
| **Deadline explícito** | +4 | Fecha/hora límite verificable |
| **Mención directa al usuario** | +3 | Nombra al usuario por nombre |
| **Hilo esperando respuesta del usuario** | +5 | El usuario es el blocker |
| **Sender bulk / unsubscribe** | -4 | Header unsubscribe o sender masivo |
| **Sin acción y sin info nueva** | -5 | No pide nada y no aporta novedad |

### 4.B — Criterios epistémicos (30 criterios, 5 ejes)

El modelo evalúa cada correo contra los criterios epistémicos definidos en
`config.yaml` bajo la sección `criterios_epistemicos`. La evaluación produce
5 subpuntuaciones que se suman para obtener el score final.

#### Los 5 ejes de evaluación

Cada criterio epistémico contribuye a uno o más de estos ejes:

| Eje | Rango | Qué mide |
|-----|-------|----------|
| **valor_decisional** | 0..10 | ¿Cambia una decisión, predicción o acción? |
| **calidad_epistemica** | -10..10 | ¿La evidencia es nueva, verificable, bien razonada? |
| **riesgo_manipulacion** | -10..0 | ¿El remitente optimiza para influir, no para informar? |
| **coste_cognitivo** | -5..0 | ¿Cuánto esfuerzo mental requiere procesarlo? |
| **presion_accion** | 0..10 | ¿Requiere respuesta/acción con consecuencias reales? |

**Fórmula:**
`score_final = valor_decisional + calidad_epistemica + riesgo_manipulacion + coste_cognitivo + presion_accion + puntos_hard_rules`

#### Catálogo de 30 criterios epistémicos

Evalúa cada criterio aplicable. Los criterios están organizados en 4 grupos:

**GRUPO A — Criterio base (valor de información)**

| # | Criterio | Pregunta operativa | Sube/Baja |
|---|----------|--------------------|-----------|
| 1 | **Cambia algo concreto** | ¿Leer esto cambiaría algo concreto que vaya a hacer? | SUBE |

**GRUPO B — Actualización bayesiana**

| # | Criterio | Pregunta operativa | Sube/Baja |
|---|----------|--------------------|-----------|
| 2 | **Cambio de predicciones** | ¿Altera mis predicciones sobre hoy/esta semana/este proyecto? | SUBE |
| 3 | **Sorpresa bayesiana** | ¿Qué tan inesperada es esta información? | SUBE |
| 4 | **Evidencia filtrada** | ¿Cuál es el algoritmo del remitente al enviarme esto? | BAJA |
| 5 | **Forward vs backward flow** | ¿Explora una solución o valida una decisión ya tomada? | SUBE/BAJA |

**GRUPO C — Diseño atencional y utilidad**

| # | Criterio | Pregunta operativa | Sube/Baja |
|---|----------|--------------------|-----------|
| 6 | **Retorno atencional** | ¿Es buena inversión de mis próximos 2 minutos? | SUBE/BAJA |
| 7 | **Confusión productiva** | ¿Revela discrepancia entre lo esperado y lo real? | SUBE |
| 8 | **Impacto causal real** | Si actúo, ¿cuánto cambia realmente el resultado? | SUBE |
| 9 | **Ruido social** | ¿Modifica algo real o solo cumple función social/ritual? | BAJA |
| 10 | **Apertura de opciones** | ¿Abre una opción valiosa que antes no tenía? | SUBE |
| 11 | **Distancia inferencial** | ¿Cuánto trabajo mental cuesta entenderlo de verdad? | BAJA |
| 12 | **Agente estratégico** | ¿El remitente optimiza para verdad o para influirme? | BAJA |
| 13 | **Densidad informativa** | ¿Cuánta información nueva por línea aporta? | SUBE/BAJA |
| 14 | **Urgencia real vs fabricada** | ¿Urgencia respaldada por consecuencias o solo por tono? | SUBE/BAJA |
| 15 | **Relevancia longitudinal** | ¿Mi yo de dentro de un mes agradecerá haber leído esto? | SUBE |

**GRUPO D — Anti-sesgo y calidad argumentativa**

| # | Criterio | Pregunta operativa | Sube/Baja |
|---|----------|--------------------|-----------|
| 16 | **Motivated stopping** | ¿Me empuja a cerrar demasiado pronto una cuestión? | BAJA |
| 17 | **Motivated continuation** | ¿Prolonga artificialmente una decisión que ya podría cerrarse? | BAJA |
| 18 | **True rejection** | ¿La objeción es sustantiva o solo una excusa elegante? | SUBE/BAJA |
| 19 | **Third alternative** | ¿Me empuja a elegir A o B cuando existe C? | SUBE |
| 20 | **Privileging the hypothesis** | ¿Eleva una hipótesis sin evidencia suficiente? | BAJA |
| 21 | **Proper humility** | ¿La duda viene con mitigación concreta o paraliza? | SUBE/BAJA |
| 22 | **Positive bias** | ¿Solo trae casos a favor o también enfrenta objeciones? | BAJA |
| 23 | **Argument screens off authority** | ¿Trae evidencia/argumento o solo rango/cargo? | SUBE/BAJA |
| 24 | **Hug the query** | ¿Está pegado a la decisión real o es contexto tangencial? | SUBE/BAJA |
| 25 | **Semantic stopsigns** | ¿Usa jerga/etiquetas para cerrar la investigación? | BAJA |
| 26 | **Fake justification** | ¿La conclusión parece anterior al razonamiento? | BAJA |
| 27 | **Fake optimization criteria** | ¿El criterio de decisión parece oportunista? | BAJA |
| 28 | **Entangled truths** | ¿Está anclado a hechos verificables (tickets, fechas, métricas)? | SUBE/BAJA |
| 29 | **Cached thought** | ¿Es pensamiento original o plantilla repetida? | SUBE/BAJA |
| 30 | **Absence of expected evidence** | ¿Falta una pieza que debería estar si fuese tan importante? | BAJA |

#### Criterios prioritarios para v3.0

No todos los criterios pesan igual. Los **12 criterios core** que SIEMPRE deben
evaluarse (equilibran valor informacional, utilidad práctica, detectabilidad
y capacidad de explicación):

1. `cambia_algo_concreto` (1)
2. `cambio_predicciones` (2)
3. `sorpresa_bayesiana` (3)
4. `evidencia_filtrada` (4)
5. `forward_backward_flow` (5)
6. `impacto_causal_real` (8)
7. `urgencia_real_vs_fabricada` (14)
8. `argument_screens_off_authority` (23)
9. `hug_the_query` (24)
10. `semantic_stopsigns` (25)
11. `entangled_truths` (28)
12. `absence_of_expected_evidence` (30)

Los 18 restantes se evalúan cuando el correo lo amerita (ej: `motivated_stopping`
solo aplica si el correo propone cerrar una cuestión abierta).

### 4.C — Routing por tiers

El score final determina el tier. Los umbrales son configurables en `config.yaml`:

| Tier | Score mínimo | Qué significa | Acción |
|------|-------------|---------------|--------|
| **reply_needed** | ≥ 10 | Requiere respuesta o acción directa | Mover a `carpetas.destino` + marcar |
| **review** | 4–9 | Vale la pena leer con atención | Mover a `carpetas.destino` |
| **reading_later** | 0–3 | Interesante pero no urgente | Dejar en `carpetas.pendiente` |
| **archive** | < 0 | Ruido, ritual o manipulación | Archivar o dejar (según modo) |

**Condiciones especiales para reply_needed** (cualquiera dispara el tier):
- Pregunta directa al usuario
- Deadline explícito en las próximas 72 horas
- Hilo donde el usuario es el blocker
- Score ≥ 10

### 4.D — Evaluación con acceso al cuerpo

Cuando se dispone del extracto del cuerpo (propiedad `content` de Mail.app
o `body` de Gmail MCP):

1. **Primer filtro rápido** — Evaluar asunto + remitente (hard rules + criterios 1-5)
2. **Si score parcial >= 1** — Analizar extracto del cuerpo con los 12 criterios core
3. **Si score parcial < 1 y remitente no está en ignorar** — Leer el extracto
   igualmente, pero el cuerpo debe aportar >= 4 puntos para alcanzar `review`

Este enfoque en dos pasadas evita procesar en profundidad correos que
claramente no son relevantes, pero no descarta correos con asuntos vagos
que podrían tener contenido valioso.

### 4.E — Explicación por correo

Cada correo DEBE incluir una explicación legible de por qué cae en su tier.
Esto no es opcional: sin explicación, el scoring se vuelve opaco.

**Formato:**
- Top 3 razones que suben prioridad
- Top 3 razones que bajan prioridad
- Rationale breve en español llano

### 4.F — Formato de presentación

```
📧 [Asunto]
   De: [Remitente] | Fecha: [DD/MM]
📝 Resumen: [2-3 líneas del contenido real]
📊 Puntuación: X (desglose: decisional +N, epistémica +N, manipulación N, cognitivo N, acción +N)
🏷️ Tier: [REPLY_NEEDED | REVIEW | READING_LATER | ARCHIVE]
   ▲ [razón positiva 1] | [razón positiva 2] | [razón positiva 3]
   ▼ [razón negativa 1] | [razón negativa 2] | [razón negativa 3]
💬 [Rationale en español llano: 1-2 frases]
🔵 Recomendación: MOVER → [destino] / DEJAR / ARCHIVAR
```

### 4.G — Control de flujo según modo

**Modo `confirmacion`** (por defecto):
- Un correo a la vez, espera Sí/No antes de mover
- Si el usuario corrige el tier, registrar como `user_override`

**Modo `lote`**:
- Presenta todos agrupados por tier, pide confirmación global
- "¿Muevo los marcados? Puedes excluir por número o cambiar tier"

**Modo `silencioso`**:
- Mueve automáticamente según tier
- Presenta resumen al final con desglose por tier

### 4.H — Gestión de escala

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
RESUMEN DE TRIAJE v3.0
───────────────────────────────────
📥 Bandeja de entrada: X correos revisados
   → Y urgentes identificados

📂 [Carpeta pendiente]: X correos revisados

   Distribución por tier:
   🔴 REPLY_NEEDED: N correos → movidos a [destino]
   🟡 REVIEW:       N correos → movidos a [destino]
   🔵 READING_LATER: N correos → dejados en [pendiente]
   ⚪ ARCHIVE:       N correos → archivados / dejados

📊 Scoring:
   Puntuación media: X.X | Máxima: X | Mínima: X
   Ejes dominantes: [eje con más peso en esta sesión]

📈 Criterios más activados:
   ▲ [criterio positivo más frecuente]: N veces
   ▲ [criterio positivo 2]: N veces
   ▼ [criterio negativo más frecuente]: N veces
   ▼ [criterio negativo 2]: N veces

🔄 Correcciones del usuario: N (si hubo overrides)
───────────────────────────────────
```

---

## Errores comunes a evitar

- No asumas que "urgente" en el asunto = urgente real (criterio 14: urgencia fabricada)
- No muevas sin confirmación en modo `confirmacion`
- Si no puedes acceder a una carpeta, informa y pide verificar el nombre
- No confundas "interesante" con "valioso" — el criterio es impacto, no curiosidad
- Si `content` devuelve HTML crudo, extrae el texto ignorando tags
- Si `content` falla, continúa el triaje solo con asunto/remitente (modo degradado)
- Al mover en lote, procesa índices de mayor a menor
- Si la calibración da un perfil incoherente, informa y sugiere acotar
- **SIEMPRE incluir explicación** — un score sin rationale es teatro, no triage
- No evalúes los 30 criterios por igual: los 12 core siempre, el resto contextual
- Si el usuario corrige un tier, registra el override para mejorar futuras sesiones
- No ignores la ausencia de evidencia (criterio 30) — lo que falta también informa

---

## Dependencias

| Proveedor | Conector necesario | Notas |
|-----------|-------------------|-------|
| iCloud    | Control your Mac (osascript) | Mail.app con cuenta configurada |
| Gmail     | Gmail MCP | Conector en Claude/Cowork |
| Otro      | Según disponibilidad | El skill preguntará |

---

## Personalización (ver config.yaml)

### Filtros y keywords (heredados de v2.0)
- `remitentes_prioritarios` — hard rule (+3)
- `remitentes_ignorar` — skip total (-99)
- `palabras_clave_boost` — con peso: `alto` (+3), `medio` (+2), `bajo` (+1)
- `palabras_clave_penalizar` — reducen puntuación (-2)
- `limite_por_sesion` — máximo por ejecución (default: 50)
- `leer_cuerpo` — `true`/`false`, activa lectura del contenido del email

### Tiers y umbrales (nuevo en v3.0)
- `tiers.reply_needed` — umbral mínimo para tier de respuesta (default: 10)
- `tiers.review` — umbral mínimo para revisión (default: 4)
- `tiers.reading_later` — umbral mínimo para lectura futura (default: 0)
- `tiers.archive` — todo lo que quede por debajo (default: -1)

### Criterios epistémicos (nuevo en v3.0)
- Los 30 criterios con sus pesos están definidos en `criterios_epistemicos`
- Se pueden activar/desactivar individualmente con `activo: true/false`
- Los pesos son ajustables por el usuario

### Telemetría (nuevo en v3.0)
- `telemetria.guardar_vector` — guarda feature vector por correo
- `telemetria.guardar_score` — guarda score final
- `telemetria.guardar_explicacion` — guarda rationale
- `telemetria.guardar_correccion` — registra overrides del usuario
