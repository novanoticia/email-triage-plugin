<!-- Referencia del PASO 4.K (v3.15). El SKILL.md deja un stub con la condición de
entrada y la regla de respuesta segura, que debe estar siempre en contexto. -->

## 4.K — Interfaz de revisión (NUEVO en v3.15)

Rige la presentación y las confirmaciones de toda sesión con una persona delante
(no la rutina). Prevalece sobre 4.F y sobre el «uno a uno» de 4.G; 4.F queda como
formato de **detalle**.

**Progreso.** Cada lectura de Mail puede tardar 60-180 s. Emite un hito de una línea
al empezar y al terminar cada fase de lectura, nunca más de uno por paso:

```
⏳ Leyendo [carpeta]…
📥 [carpeta]: N correos
⏳ Cuerpos: N/M
```

**Numeración estable.** Numera cada unidad (correo o hilo) con `#N` en el orden en que
la presentas, una sola vez por sesión, y conserva la tabla `#N → message-id(s)`. Los
números no se reasignan aunque cambie un tier: toda respuesta de la persona, el registro
(PASO 4.I) y el informe (PASO 5.R) se resuelven por esa tabla, nunca por la posición del
correo en la carpeta.

**Formato compacto (por defecto).** Una tabla por tier, en el orden 🔴 🟡 🔵 ⚪, con
una línea por unidad:

```
[🔴|🟡|🔵|⚪] [TIER] (N) → [destino]
| # | Correo | Score | ▲ / ▼ |
| #N | [Asunto] · [Remitente] · [DD/MM] | X | ▲ [razón] · ▼ [razón] |
```

El formato completo de 4.F se reserva para `REPLY_NEEDED` y para cuando la persona pide
`detalle #N`. Con más de 10 unidades en `READING_LATER` o `ARCHIVE`, agrupa por
remitente en una línea por grupo.

**Confirmación por tier.** Una sola pregunta por cada tier que se mueve (`REVIEW`,
`ARCHIVE` y `REPLY_NEEDED` si su destino no es el origen); `READING_LATER` no se pregunta
porque no se mueve. Si el cliente ofrece preguntas con opciones, úsalas con estas tres:
«Sí, los [N] / Sí, excepto… / No». Si no, pregunta en texto:

"¿Muevo [N] correos de [tier] a [destino]? Responde sí, no o una corrección: #N se queda, #N → otro tier."

**Respuestas aceptadas.** Además del sí y el no, las de `entrada.correcciones`, varias
en una línea separadas por comas; el tier vale en mayúsculas o minúsculas:
- `mueve todo` → aplica la propuesta completa
- `solo REVIEW` / `solo ARCHIVE` → solo ese tier
- `#N se queda` → excluye esa unidad del movimiento
- `#N → REVIEW` (o el tier que sea) → cambia el tier; es una corrección: regístrala en
  `correcciones.jsonl` en el momento (PASO 5.B)
- `detalle #N` → muestra esa unidad con el formato 4.F; no mueve nada

**Respuesta segura (no negociable).** Solo un sí explícito mueve correo. Una respuesta
vacía, sin opción elegida, ambigua o que no encaja en la lista anterior **no mueve
nada**: dilo en una línea y vuelve a preguntar una sola vez:

"No he movido nada: necesito un sí explícito o una corrección (#N se queda, #N → otro tier)."

Si la segunda respuesta tampoco es explícita, cierra sin mover y presenta el resumen.
El silencio nunca es aceptación.
