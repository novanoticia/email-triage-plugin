---
name: email-triage
description: >
  Triaje inteligente de correo electrónico: analiza bandejas de entrada y carpetas
  de lectura pendiente para identificar correos de alto valor usando un criterio
  de "valor diferencial" (¿leer esto cambiaría algo concreto para el usuario?).
  Soporta iCloud (Mail.app vía AppleScript), Gmail (vía MCP) y cualquier cliente
  compatible con Cowork. Incluye calibración opcional basada en historial de correos
  conservados.
  Actívalo cuando el usuario diga "filtra mi correo", "revisa mi bandeja",
  "triaje de emails", "qué correos son importantes", "email triage",
  "clasifica mis correos", "qué debería leer", "hay algo urgente en mi correo",
  "revisa Leer Después", "filtra newsletters", o cualquier petición que implique
  evaluar, priorizar o clasificar correos electrónicos.
  También se activa si el usuario pide mover correos entre carpetas basándose
  en relevancia o importancia.
---

# Email Triage — Filtrado inteligente de correo por valor diferencial

## Qué hace este skill

Evalúa correos electrónicos usando un criterio epistémico: no "¿es importante?"
sino **"¿leer esto cambiaría algo concreto para el usuario?"**. Es la diferencia
entre un filtro de relevancia y un filtro de impacto real.

El skill opera en tres fases opcionales (calibración, urgentes, triaje profundo)
y se adapta a cualquier perfil profesional y proveedor de correo.

---

## PASO 0 — Leer la configuración del usuario

Antes de ejecutar cualquier fase, lee el archivo `config.yaml` que acompaña
a este skill. Contiene el perfil del usuario y la configuración de carpetas.

Si no existe `config.yaml`, pide al usuario que configure estos campos mínimos
antes de continuar:

1. **nombre**: cómo dirigirse al usuario
2. **perfil**: descripción breve de su rol, formación e intereses (2-3 líneas)
3. **proyectos_activos**: lista de proyectos, herramientas o plataformas que usa
4. **proveedor_correo**: `icloud`, `gmail` u `otro`
5. **carpetas**: nombres de las carpetas del usuario (ver estructura en config.yaml)
6. **modo_interaccion**: `confirmacion` (uno a uno), `lote` (todos de golpe) o `silencioso`

El perfil del usuario es la referencia contra la que se evalúa cada correo.
Sin perfil, el criterio de valor diferencial no tiene ancla.

---

## PASO 1 — Detectar el proveedor de correo y conectar

### iCloud / Mail.app (macOS)

Usa el conector "Control your Mac" (osascript) para acceder a Mail.app.

Para listar correos de una carpeta:
```applescript
tell application "Mail"
    set targetMailbox to mailbox "NOMBRE_CARPETA" of account "iCloud"
    set msgs to messages of targetMailbox
    -- Leer asunto, remitente, fecha, extracto del cuerpo
end tell
```

Para mover un correo entre carpetas:
```applescript
tell application "Mail"
    set targetMailbox to mailbox "DESTINO" of account "iCloud"
    move theMessage to targetMailbox
end tell
```

### Gmail (vía MCP)

Usa las herramientas Gmail MCP disponibles en Cowork. Flujo verificado:

**Paso 1 — Listar correos** con `gmail_search_messages`:
- Acepta query con sintaxis Gmail estándar (ej: `label:Leer-Despues`)
- Devuelve: `messageId`, `threadId`, `snippet` (extracto breve), headers
  (From, Date, Subject, To) y `sizeEstimate`
- El `snippet` es suficiente para un primer filtro por asunto/remitente
- Soporta paginación con `nextPageToken` y `maxResults` (hasta 500)

**Paso 2 — Leer cuerpo completo** con `gmail_read_message`:
- Requiere el `messageId` obtenido en el paso anterior
- Devuelve el campo `body` con el texto completo del correo (plaintext)
- También devuelve `attachments` con nombre, tipo MIME y tamaño
- No hay límite práctico de longitud en el cuerpo devuelto
- IMPORTANTE: usa este paso solo para correos que pasan el filtro
  inicial por snippet/asunto, para no sobrecargar la sesión

**Paso 3 — Mover correos** entre etiquetas:
- Gmail no tiene carpetas; usa etiquetas (labels)
- Para "mover": añade la etiqueta destino y elimina la de origen
- El usuario debe crear las etiquetas previamente en Gmail

### Otro proveedor

Si el conector disponible es distinto, adapta el acceso usando las herramientas
MCP o AppleScript que el usuario tenga configuradas. El skill debe preguntar
qué conectores están disponibles si no puede determinarlos automáticamente.

---

## PASO 2 — CALIBRACIÓN (opcional, recomendada la primera ejecución)

La calibración construye un perfil de preferencias a partir del historial
del usuario. Funciona con cualquier carpeta que contenga correos que el
usuario haya decidido conscientemente conservar.

### Procedimiento

1. Accede a la carpeta definida como `carpeta_historial` en la configuración.
2. Analiza los últimos 100 correos (o los disponibles, si hay menos).
3. Extrae patrones silenciosamente:
   - Remitentes que aparecen 3+ veces (señal de fuente de confianza)
   - Temáticas recurrentes (palabras clave, dominios)
   - Tipos de contenido (newsletters, notificaciones, comunicaciones directas)
   - Ventanas horarias habituales
4. Almacena el perfil internamente como referencia adicional para las fases
   siguientes. No lo muestres salvo que el usuario pida `mostrar_calibracion`.
5. Confirma: "He revisado X correos en '[nombre_carpeta]'. Calibración lista."

### Cuándo recalibrar

- Si el usuario lo pide explícitamente
- Si el skill detecta que sus recomendaciones no coinciden con las decisiones
  del usuario (más de 3 "No" consecutivos en modo confirmación)

### Nota sobre la calidad de la calibración

Si la carpeta de historial contiene correos conservados por razones muy
heterogéneas (fiscales, sentimentales, profesionales), el perfil resultante
puede ser ruidoso. En ese caso, informa al usuario y sugiere acotar por
rango de fechas o excluir ciertos remitentes.

---

## PASO 3 — BANDEJA DE ENTRADA (detección de urgentes)

Accede a la carpeta definida como `carpeta_entrada` en la configuración.
Revisa los correos recientes (últimas 48-72 horas).

### Criterio de urgencia

Un correo es urgente si cumple AMBAS condiciones:
1. Tiene una ventana de tiempo corta (deadline, evento próximo, oferta que expira)
2. Es relevante para el perfil del usuario (no cualquier deadline)

### Formato de presentación

Para cada candidato urgente:

```
📬 [Asunto]
   De: [Remitente]
📝 Resumen: [2-3 líneas del contenido real]
⚡ Por qué ahora: [1 línea — qué ventana temporal tiene]
🔵 Recomendación: LEER AHORA / PUEDE ESPERAR
```

En modo `confirmacion`: espera respuesta antes de pasar al siguiente.
En modo `lote`: presenta todos juntos y pide confirmación global.
En modo `silencioso`: actúa según la recomendación sin preguntar.

Si no hay nada urgente:
"Nada en la bandeja requiere atención inmediata."

---

## PASO 4 — TRIAJE PROFUNDO (carpeta de lectura pendiente)

Esta es la fase principal. Revisa la carpeta definida como `carpeta_pendiente`.

### El criterio de valor diferencial

La pregunta central NO es "¿es importante?" sino:

**¿Leer esto cambiaría algo concreto para el usuario?
¿Lo diferenciaría de alguien de su entorno que no lo haya leído?**

Para evaluar cada correo, sigue esta secuencia de preguntas en orden.
Detente en la primera que responda "sí":

```
1. ¿Requiere acción con fecha límite real?
   → SÍ: MOVER (categoría: ACCIÓN)

2. ¿Modifica una decisión o plan activo del usuario?
   → SÍ: MOVER (categoría: OPERATIVO)

3. ¿Contiene conocimiento técnico o conceptual aplicable
   a sus proyectos activos?
   → SÍ: MOVER (categoría: ESTRATÉGICO)

4. ¿Afecta a herramientas o plataformas que usa directamente?
   → SÍ: MOVER (categoría: HERRAMIENTAS)

5. ¿Ofrece perspectiva analítica que le daría ventaja real
   sobre alguien que no lo ha leído?
   → SÍ: MOVER (categoría: VENTAJA)

6. ¿El remitente tiene peso histórico (aparece frecuentemente
   en la carpeta de historial, si se calibró)?
   → SÍ: evalúa con umbral más bajo, pero no mueve automáticamente.
   Solo inclina la balanza si hay duda.

7. Ninguna de las anteriores.
   → DEJAR
```

### Señales claras de DEJAR (no mover)

- Información general fácilmente recuperable con una búsqueda web
- Confirmaciones, recibos o notificaciones de estado sin acción requerida
- Eco de algo que el usuario ya conoce (repetición de otra fuente)
- El valor del contenido caducaría antes de que el usuario pudiera actuar
- Newsletter genérica sin contenido aplicable a sus proyectos

### Formato de presentación

Para cada correo evaluado:

```
📧 [Asunto]
   De: [Remitente] | Fecha: [DD/MM]
📝 Resumen: [2-3 líneas del contenido real, no del asunto]
⚖️ Razón: [1-2 líneas — criterio que aplica y por qué]
🏷️ Categoría: [ACCIÓN | OPERATIVO | ESTRATÉGICO | HERRAMIENTAS | VENTAJA]
🔵 Recomendación: MOVER / DEJAR
```

### Control de flujo según modo de interacción

**Modo `confirmacion`** (por defecto):
- Presenta un correo a la vez
- Pregunta: "¿Lo muevo a '[carpeta_destino]'? → Sí / No"
- Solo mueve si el usuario responde "Sí", "S", "sí" o equivalente
- Espera respuesta antes de continuar con el siguiente

**Modo `lote`**:
- Presenta todos los correos con sus recomendaciones
- Al final, lista los recomendados para mover con número
- Pregunta: "¿Muevo los marcados? Puedes excluir por número (ej: 'todos menos 3 y 7')"

**Modo `silencioso`**:
- Mueve automáticamente los que recomienda
- Al final, presenta un resumen de lo movido y lo dejado
- PRECAUCIÓN: solo usar si el usuario confía en la calibración tras varias ejecuciones

### Gestión de escala

Si la carpeta de lectura pendiente tiene más de 30 correos:
- Informa al usuario del volumen
- Sugiere procesar en lotes de 15
- Prioriza correos más recientes primero (los más antiguos tienen mayor
  probabilidad de haber perdido vigencia)

---

## PASO 5 — RESUMEN DE SESIÓN

Al finalizar, presenta un resumen:

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
───────────────────────────────────
```

---

## Errores comunes a evitar

- No asumas que todo lo que tiene "urgente" en el asunto es realmente urgente.
  Muchas newsletters usan esa palabra como clickbait.
- No muevas correos sin confirmación en modo `confirmacion`, ni siquiera
  si estás muy seguro. El usuario es quien decide.
- Si no puedes acceder a una carpeta (permisos, nombre incorrecto), informa
  y pide al usuario que verifique el nombre exacto.
- No confundas "interesante" con "valioso". El criterio es impacto, no curiosidad.
- Si la calibración da un perfil incoherente, dilo. Es mejor recalibrar
  con un rango más estrecho que operar con datos ruidosos.

---

## Dependencias

El skill se adapta a los conectores disponibles:

| Proveedor | Conector necesario | Notas |
|-----------|-------------------|-------|
| iCloud    | Control your Mac (osascript) | Mail.app debe tener la cuenta configurada |
| Gmail     | Gmail MCP | Disponible como conector en Claude |
| Otro      | Depende del cliente | El skill preguntará qué herramientas hay disponibles |

---

## Personalización avanzada

El usuario puede añadir en `config.yaml`:

- `remitentes_prioritarios`: lista de direcciones que siempre se evalúan con umbral bajo
- `remitentes_ignorar`: lista de direcciones que se saltan siempre
- `palabras_clave_boost`: términos que aumentan la probabilidad de MOVER
- `palabras_clave_penalizar`: términos que la reducen
- `limite_por_sesion`: máximo de correos a procesar por ejecución (default: 30)
- `idioma_resumen`: idioma para los resúmenes (default: mismo que el perfil)
