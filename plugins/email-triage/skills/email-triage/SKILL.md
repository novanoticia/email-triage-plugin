---
name: email-triage
version: "3.1.0"
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

# Email Triage v3.1 — Filtrado epistémico por valor diferencial

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
el HTML en bruto. **ANTES de usar el extracto para cualquier evaluación, DEBE
pasar por el pipeline de sanitización descrito en "PASO 1.B — Sanitización del
cuerpo"**. Si `content` falla (error de permisos o formato), el bloque
`try/on error` asegura que el triaje continúa solo con asunto y remitente.

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

#### Mover múltiples correos por índice (lote) — PATRÓN SEGURO

⚠️ **NO uses el patrón de iterar índices de mayor a menor**. Aunque la
documentación clásica lo recomienda, en producción falla cuando hay más
de un lote o movimientos previos en la misma sesión.

**Patrón verificado en producción**: capturar las referencias a los objetos
mensaje ANTES de mover ninguno, y luego mover las referencias:

```applescript
tell application "Mail"
    set acct to account "NOMBRE_CUENTA"
    set sourceMailbox to mailbox "CARPETA_ORIGEN" of acct
    set destMailbox to mailbox "CARPETA_DESTINO" of acct

    -- 1. Capturar TODOS los mensajes como lista de referencias
    set todosMsg to every message of sourceMailbox

    -- 2. Seleccionar los que queremos mover por sus índices originales
    set indicesToMove to {45, 32, 18, 7, 3}
    set mensajesAMover to {}
    repeat with idx in indicesToMove
        set end of mensajesAMover to (item idx of todosMsg)
    end repeat

    -- 3. Mover las referencias (el orden ya no importa)
    set movidos to 0
    repeat with m in mensajesAMover
        try
            move m to destMailbox
            set movidos to movidos + 1
        end try
    end repeat

    return "Movidos: " & movidos & " de " & (count of mensajesAMover)
end tell
```

**Por qué funciona**: al capturar `every message` como lista, AppleScript
mantiene referencias internas a cada objeto mensaje. Cuando mueves uno,
las referencias de los demás siguen apuntando al mensaje correcto, no a
una posición numérica que haya cambiado.

**IMPORTANTE**: Si previamente se han movido correos de la misma carpeta
en la misma sesión, los índices originales habrán cambiado. Siempre
recaptura `every message` antes de cada lote de movimientos.

#### Caracteres especiales en nombres de carpeta (bug conocido)

⚠️ Los nombres de carpeta con acentos u otros caracteres no-ASCII
(ej: "Leer Después", "Correo sí deseado") **fallan** cuando se pasan
como AppleScript inline al conector osascript.

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

Flujo verificado con herramientas Gmail MCP:

1. **Listar** con `gmail_search_messages` — query Gmail estándar, paginación
   con `nextPageToken`, `maxResults` hasta 500
2. **Leer cuerpo** con `gmail_read_message` — solo para correos que pasan
   el filtro inicial por snippet/asunto (evita sobrecargar la sesión)
3. **Mover** entre etiquetas — añadir destino, eliminar origen

### Otro proveedor

Preguntar al usuario qué conectores MCP o AppleScript tiene disponibles.

---

## PASO 1.B — SANITIZACIÓN DEL CUERPO (obligatorio antes de evaluar)

Todo extracto de cuerpo (`content` de Mail.app, `body` de Gmail MCP, o cualquier
otra fuente) **DEBE** pasar por este pipeline de limpieza ANTES de llegar al
motor de evaluación epistémica. Sin esta sanitización, los criterios como
`densidad_informativa`, `hug_the_query` o `sorpresa_bayesiana` evaluarán basura
(CSS, HTML, Base64, firmas corporativas) como si fuera contenido real, generando
falsos positivos y desperdiciando tokens.

### Pipeline de sanitización (aplicar en orden)

**Paso S1 — Eliminar cadenas de respuestas (reply chains)**

Cortar el texto en la PRIMERA ocurrencia de cualquiera de estos marcadores:
- `On ... wrote:` / `El ... escribió:`
- `---------- Forwarded message ----------`
- `> ` al inicio de 3+ líneas consecutivas (quoted text)
- `From:` seguido de una dirección de email (cabecera de reenvío)
- `_____` (5+ guiones bajos, separador típico de Outlook)

Quedarse SOLO con el mensaje más reciente. El contexto histórico del hilo no
aporta al triaje y puede multiplicar los tokens por 5-10x.

**Paso S2 — Strip HTML**

Si el extracto contiene etiquetas HTML (`<div>`, `<table>`, `<span>`, `<style>`,
`<head>`, `<!DOCTYPE`, etc.):

1. Eliminar completamente bloques `<style>...</style>` y `<script>...</script>`
2. Eliminar todas las etiquetas HTML, conservando solo el texto entre ellas
3. Convertir entidades HTML comunes: `&nbsp;` → espacio, `&amp;` → `&`,
   `&lt;` → `<`, `&gt;` → `>`, `&#39;` → `'`, `&quot;` → `"`
4. Colapsar múltiples espacios/líneas vacías consecutivas en un solo salto de línea

Si tras la limpieza el texto útil tiene menos de 30 caracteres, marcar como
`[cuerpo no legible — HTML sin texto plano]`.

**Paso S3 — Decodificar Base64**

Si el extracto contiene bloques de texto que parecen Base64 (líneas largas de
caracteres alfanuméricos+/= sin espacios, típicamente >76 caracteres por línea):

- No intentar decodificar — marcar como `[contenido codificado Base64]`
- Tratar el correo como `[solo metadatos]` para la evaluación epistémica
- Es preferible evaluar sin cuerpo que evaluar basura codificada

**Paso S4 — Eliminar firmas y disclaimers**

Cortar el texto en la PRIMERA ocurrencia de:
- `--` al inicio de línea seguido de contenido de firma (nombre, cargo, teléfono)
- `Enviado desde mi iPhone` / `Sent from my iPhone` / variantes de dispositivo
- `Este mensaje es confidencial` / `This email is confidential` / disclaimers legales
- Bloques con 3+ líneas consecutivas que solo contienen: nombre, cargo, empresa,
  teléfono, dirección, URL, o iconos de redes sociales

**Paso S5 — Validación final**

Tras aplicar S1-S4, verificar:
- Si el texto resultante tiene menos de 30 caracteres útiles → `[cuerpo no legible]`
- Si el texto resultante supera 1500 caracteres → truncar a 1500 + `[truncado]`
- Si el texto resultante tiene ratio de caracteres especiales (no alfanuméricos
  ni espacios) > 40% → `[cuerpo corrupto]` y usar solo metadatos

### Etiquetas de estado del cuerpo

Cada correo procesado DEBE llevar una de estas etiquetas internas:

| Etiqueta | Significado | Evaluación |
|----------|-------------|------------|
| `[texto limpio]` | Cuerpo sanitizado con éxito | Evaluación completa (30 criterios) |
| `[HTML detectado]` | Se extrajo texto de HTML | Evaluación completa, -1 en densidad_informativa |
| `[cuerpo no legible]` | HTML sin texto plano extraíble | Solo hard rules + criterios 1-5 |
| `[contenido codificado Base64]` | Cuerpo codificado | Solo metadatos |
| `[cuerpo corrupto]` | Ratio de basura > 40% | Solo metadatos |
| `[solo metadatos]` | No se pudo leer el cuerpo | Solo hard rules + criterios 1-5 + criterio 28 |
| `[sin acceso al cuerpo]` | Error de permisos/timeout | Solo metadatos |

### Feedback al usuario

Al final de cada sesión de triaje, si hubo correos con cuerpos problemáticos,
informar una sola vez:

> "N correos tenían cuerpo HTML/codificado sin texto plano extraíble.
> Se analizaron por metadatos. Si quieres mejor precisión para estos remitentes,
> configura tu cliente de correo para solicitar text/plain o añádelos a
> `remitentes_prioritarios` para forzar lectura detallada en futuras sesiones."

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

El score final determina el tier. Los umbrales son configurables en `config.yaml`.
Cada tier tiene un **indicador de color** (banderita) para identificación visual rápida:

| Tier | Indicador | Score mínimo | Qué significa | Acción |
|------|-----------|-------------|---------------|--------|
| **REPLY_NEEDED** | 🔴 (rojo) | ≥ 10 | Requiere respuesta o acción directa | Mover a `carpetas.destino_reply_needed` (o `destino`) + marcar |
| **REVIEW** | 🟡 (amarillo) | 4–9 | Vale la pena leer con atención | Mover a `carpetas.destino` |
| **READING_LATER** | 🔵 (azul) | 0–3 | Interesante pero no urgente | Dejar en `carpetas.pendiente` |
| **ARCHIVE** | ⚪ (gris) | < 0 | Ruido, ritual o manipulación | Mover a `carpetas.destino_archive` si está definido; si no, archivar nativamente (según modo) |

**Uso obligatorio de indicadores**: En TODA presentación de resultados (correo
individual, tabla resumen, resumen de sesión), el tier DEBE ir acompañado de
su indicador de color. Esto permite al usuario escanear visualmente la prioridad
sin leer el texto.

**Condiciones especiales para reply_needed** (cualquiera dispara el tier):
- Pregunta directa al usuario
- Deadline explícito en las próximas 72 horas
- Hilo donde el usuario es el blocker
- Score ≥ 10

### 4.D — Evaluación con acceso al cuerpo

**Prerrequisito**: el extracto del cuerpo DEBE haber pasado por el pipeline
de sanitización del PASO 1.B antes de llegar aquí. La evaluación epistémica
opera SOLO sobre texto sanitizado y etiquetado.

Cuando se dispone del extracto sanitizado del cuerpo (propiedad `content` de
Mail.app o `body` de Gmail MCP, tras PASO 1.B):

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
[🔴|🟡|🔵|⚪] Tier: [REPLY_NEEDED | REVIEW | READING_LATER | ARCHIVE]
   ▲ [razón positiva 1] | [razón positiva 2] | [razón positiva 3]
   ▼ [razón negativa 1] | [razón negativa 2] | [razón negativa 3]
💬 [Rationale en español llano: 1-2 frases]
🔵 Recomendación: MOVER → [destino] / DEJAR / ARCHIVAR
```

Los colores de tier en el formato de presentación:
- `🔴 REPLY_NEEDED` — rojo: acción urgente
- `🟡 REVIEW` — amarillo: leer con atención
- `🔵 READING_LATER` — azul: lectura futura
- `⚪ ARCHIVE` — gris: descartable

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
   ⚪ ARCHIVE:       N correos → movidos a [destino_archive] / archivados / dejados

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
- Si `content` devuelve HTML crudo, aplicar pipeline de sanitización PASO 1.B completo
- Si `content` falla, continúa el triaje solo con asunto/remitente (modo degradado)
- Al mover en lote, captura las referencias antes de mover (ver patrón seguro en PASO 1)
- Si la calibración da un perfil incoherente, informa y sugiere acotar
- **SIEMPRE incluir explicación** — un score sin rationale es teatro, no triage
- No evalúes los 30 criterios por igual: los 12 core siempre, el resto contextual
- Si el usuario corrige un tier, registra el override para mejorar futuras sesiones
- No ignores la ausencia de evidencia (criterio 30) — lo que falta también informa

---

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

El truncado a 500 caracteres del cuerpo (PASO 1) es la primera línea de defensa,
pero no es suficiente si el volumen total es alto.

**Reglas adicionales:**
- Si el cuerpo extraído supera 2000 caracteres tras truncado (ej: por HTML
  expandido), truncar a 2000 y añadir `[truncado]`
- Si un correo tiene más de 50 líneas de texto plano visible, usar solo
  las primeras 30 líneas para el análisis epistémico
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
   1-5 del Grupo B, y criterio 28 (entangled truths por metadatos)
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

Si faltan campos críticos (nombre, cuenta, proveedor), no continuar hasta
que el usuario los proporcione. Presentar un setup guiado breve.

---

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
