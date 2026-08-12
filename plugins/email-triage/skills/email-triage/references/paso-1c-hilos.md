<!-- Extraído de SKILL.md por CM2 (auditoría 2026-08-07): bloque
condicional o de consulta que no toda sesión necesita. El SKILL.md deja
un stub con la condición de entrada y apunta aquí. -->

## PASO 1.C — DETECCIÓN Y AGRUPACIÓN DE HILOS

Ejecutar DESPUÉS del PASO 1.B (sanitización) y ANTES del PASO 2.
Transforma la lista plana de mensajes en unidades de evaluación: mensajes
individuales o hilos agrupados. Esto es lo que garantiza que `presion_accion`
y `hilo_esperando_respuesta` se evalúen sobre el hilo completo, no sobre
un fragmento aislado.

**Vía preferente (determinista, v3.8.19)**: para iCloud, no agrupes a ojo — la
normalización de asunto y la unión por participante compartido son
deterministas y reproducibles con `triage_helpers.py agrupar-hilos`. Pásale
los metadatos ya recogidos (SCRIPT 1A) y usa las `unidades` que devuelve:

```bash
echo '{"correos":[{"id":1,"remitente":"A <a@x.com>","asunto":"Reunión"},
                  {"id":2,"remitente":"B <x.com>","asunto":"Re: Reunión"}]}' \
  | python3 "<ruta-del-skill>/scripts/triage_helpers.py" agrupar-hilos
```

Devuelve `{"unidades":[{tipo, clave_hilo, count, participantes, miembros}]}`.
En Gmail sigue mandando el hilo nativo (paso 0 de abajo); el algoritmo manual
que sigue es la especificación que `agrupar-hilos` implementa (fallback si el
script no está disponible).

### Algoritmo de agrupación

**0. Gmail: usar el hilo nativo (v3.5)**

Si el proveedor es Gmail, NO usar la heurística de asunto: el MCP de
Gmail ya agrupa por `threadId` nativo (basado en References/In-Reply-To,
más fiable que cualquier heurística). Cada thread devuelto ES la unidad
de evaluación. Como el hilo nativo incluye también los mensajes
enviados por el usuario, `usuario_es_ultimo_en_responder` se lee
directamente del último mensaje del thread (señal con
`verificacion: nativa`). Los pasos 1-2 siguientes aplican SOLO a
iCloud/Mail.app.

**1. Normalizar el asunto de cada mensaje**

Eliminar prefijos de respuesta/reenvío para obtener el asunto raíz:
- Eliminar: `Re:`, `RE:`, `Fwd:`, `FWD:`, `RV:`, `Aw:`, `SV:`, `TR:`
  (y sus variantes con espacios o combinadas, ej: `Re: Fwd:`)
- Trim de espacios y normalizar a minúsculas
- El resultado es la `clave_hilo`

**2. Agrupar por clave_hilo + participante común**

Dos mensajes pertenecen al mismo hilo si:
- Tienen la misma `clave_hilo`, Y
- Comparten al menos un participante (el dominio del remitente de uno
  aparece como dominio del remitente del otro, o el mismo remitente exacto)

Esto evita falsos positivos con asuntos genéricos como "Hola" o "Reunión"
entre remitentes sin relación.

**3. Clasificar el resultado**

- Grupo de 1 mensaje → `tipo: individual`
- Grupo de 2+ mensajes → `tipo: hilo`, ordenar por fecha (más antiguo primero)

### Estructura del hilo

Para cada hilo detectado, construir este objeto interno:

```
HILO [clave_hilo]
  mensajes: [lista ordenada por fecha, más antiguo primero]
  count: N
  primer_mensaje: {from, date, subject original}
  ultimo_mensaje: {from, date, body_sanitizado}
  participantes: [lista de remitentes únicos]
  usuario_es_ultimo_en_responder: true / false / desconocido
    → true si el último mensaje del hilo COMPLETO (incluyendo Enviados)
      es del usuario (comparar `from` con `correo.cuenta` del config)
    → false si otro participante escribió después del último envío del
      usuario, o el usuario nunca escribió — CONFIRMADO contra Enviados
    → desconocido si no se pudo verificar
  verificacion: nativa (Gmail) / enviados (iCloud) / ninguna
```

**Verificación contra Enviados — iCloud (v3.5).** La carpeta que se está
triando no contiene tus propios envíos, así que sin este paso la señal
daría `false` para casi cualquier hilo y el +5 se aplicaría siempre
(sesgo estructural al alza). Para cada HILO detectado (no para mensajes
individuales), hacer UNA consulta acotada al buzón de Enviados.

**Regla no negociable (F1):** `clave_hilo` deriva del **asunto** (superficie
del remitente) y `correo.cuenta` de tu config. **Nunca los interpoles a mano
en el AppleScript**: una comilla en el asunto —común en correo legítimo
(`Re: "urgente"`)— rompe el literal o altera el predicado `whose`. Monta la
consulta con el mecanismo, que los escapa como `montar-mover` escapa el mover:

```bash
echo '{"cuenta":"<correo.cuenta>","clave_hilo":"<clave_hilo>","fecha_corte":"<fecha del último recibido del hilo>"}' \
  | python3 "<ruta-del-skill>/scripts/triage_helpers.py" montar-consulta-enviados
```

Escribe el `script` devuelto a un fichero temporal y ejecútalo con `osascript`;
`return (count of respuestasUsuario)` da el conteo. Si `sospechoso` no es null,
refléjalo en el resumen (el escape ya neutralizó el valor). Solo LEE, no mueve.

- count > 0 → el usuario respondió después del último recibido →
  `usuario_es_ultimo_en_responder: true`
- count = 0 → `false` (confirmado)
- error de AppleScript o buzón inaccesible → `desconocido` (NUNCA asumir
  `false` por defecto: ese era el sesgo que esta verificación corrige)

Acotar siempre con `date sent >` para que la consulta sea barata incluso
en buzones grandes. Si el lote tiene más de 10 hilos, verificar los 10
más recientes y marcar el resto como `desconocido`.

`usuario_es_ultimo_en_responder` alimenta la hard rule
`hilo_esperando_respuesta_del_usuario`: **+5 solo con `false`
confirmado; +2 si `desconocido`; 0 si `true`** (ver 4.A).

### Casos especiales

- **Asunto vacío o solo prefijos**: tratar como `tipo: individual`
  (no se puede agrupar de forma fiable)
- **Hilo con >10 mensajes**: procesar solo los últimos 5 para el análisis
  del cuerpo; el `count` real se refleja en el score (+1 por profundidad)
- **Mensajes de distintas carpetas en el mismo hilo**: posible si el usuario
  archivó parte del hilo. No agrupar entre carpetas — evaluar solo los
  mensajes presentes en la carpeta actual del triaje

### Impacto en el lote

Contar cada **hilo** como una unidad para el límite de `limite_por_sesion`,
no cada mensaje. Un hilo de 5 mensajes cuenta como 1 unidad del lote.
Informar al usuario: "N unidades procesadas (X mensajes individuales +
Y hilos con Z mensajes en total)."

---


### 4.J — Evaluación de hilos como unidad

Cuando PASO 1.C clasifica una unidad como `tipo: hilo`, aplicar este
procedimiento en lugar de evaluar cada mensaje por separado.

#### Qué se evalúa

- **Cuerpo**: usar el `body_sanitizado` del `ultimo_mensaje` (el más reciente
  es lo que el usuario necesita procesar ahora)
- **Metadatos de contexto**: usar `count`, `participantes`, y
  `usuario_es_ultimo_en_responder` para informar criterios específicos
- **Asunto**: usar el asunto del `ultimo_mensaje`
- **Remitente**: usar el remitente del `ultimo_mensaje`

#### Hard rules específicas de hilo (añadir a las de 4.A)

| Fuente | Puntos | Condición |
|--------|--------|-----------|
| **Hilo esperando respuesta** | +5 / +2 | +5 con `false` confirmado (verificación nativa o Enviados); +2 con `desconocido` |
| **Profundidad de hilo** | +1 | `count >= 3` (conversación activa) |
| **Hilo muy largo** | -1 | `count >= 10` (posible ruido acumulado) |
| **Único participante externo** | +1 | Solo hay un remitente externo (conversación directa, no lista) |

#### Criterios epistémicos afectados por el contexto de hilo

Estos criterios deben considerar el hilo completo, no solo el último mensaje:

- **`presion_accion`**: evaluar si hay una pregunta o acción pendiente del
  último mensaje *y* si el usuario no ha respondido aún. Si
  `usuario_es_ultimo_en_responder: true`, bajar `presion_accion` (ya respondió)
- **`urgencia_real_vs_fabricada`**: un hilo largo con múltiples intercambios
  sin resolución es evidencia de urgencia real, no fabricada
- **`sorpresa_bayesiana`**: si el hilo muestra un cambio de posición o nueva
  información respecto al mensaje inicial, sube este criterio
- **`relevancia_longitudinal`**: hilos con ≥3 participantes distintos suelen
  tener mayor relevancia longitudinal

#### Tier y movimiento del hilo

El tier se asigna al **hilo completo**. Al mover, mover **todos los mensajes
del hilo** juntos usando el patrón de referencias del PASO 1. Nunca mover
un mensaje de un hilo sin mover el resto — dejaría el hilo partido entre
carpetas.

En el session log (PASO 4.I), registrar una entrada por mensaje del hilo,
todas con el mismo `thread_id: [clave_hilo]`, para que el undo revierta
el hilo completo.

#### Formato de presentación de hilo

```
🧵 [Asunto raíz] — hilo de N mensajes
   Participantes: [remitente1], [remitente2]... | Último: [DD/MM] de [remitente]
   ⏳ Esperando tu respuesta: [Sí / No]
📝 Resumen del último mensaje: [2-3 líneas]
📊 Puntuación: X (decisional +N, epistémica +N, manipulación N, cognitivo N, acción +N, hilo +N)
[🔴|🟡|🔵|⚪] Tier: [REPLY_NEEDED | REVIEW | READING_LATER | ARCHIVE]
   ▲ [razón positiva 1] | [razón positiva 2] | [razón positiva 3]
   ▼ [razón negativa 1] | [razón negativa 2] | [razón negativa 3]
💬 [Rationale: 1-2 frases que mencionan explícitamente si hay respuesta pendiente]
🔵 Recomendación: MOVER hilo completo (N mensajes) → [destino] / DEJAR / ARCHIVAR
```
