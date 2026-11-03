# Diseño: remitentes de lectura

Estado: **propuesta, pendiente de las decisiones D1-D7 del mantenedor.** Nada
de esto está implementado. Redactado el 2026-11-03.

## El problema, visto con correo real

Las mediciones con correos inventados (`docs/mediciones-evaluadores.md`, 18-25)
mostraban boletines que caían a `ARCHIVE`. Los primeros ensayos con correo real
(dry-runs del mantenedor del 2026-11-03, 100 correos de su carpeta «Leer
Después», principal Claude) muestran lo contrario:

- **Los ensayos suben a `REVIEW`.** En el primer lote de 50, 7 de las 12
  unidades en `REVIEW` eran ensayos o boletines de autores que sigue; en el
  segundo, 4 de 9. `REVIEW` se mueve a la carpeta de urgentes, así que un
  ensayo sin nada que hacer acaba junto al aviso del banco.
- **`READING_LATER` sí aparece** (3 y 8 unidades), pero sin criterio estable:
  ensayos del mismo autor caen unos en `REVIEW` y otros en `ARCHIVE`.
- **Los evaluadores externos (Haiku, Jev, Decisions y Gemini) bajan esos
  mismos ensayos**, sobre todo a `ARCHIVE`. Aplican la pregunta del plugin al
  pie de la letra; el principal, con el perfil de intereses delante, puntúa
  alto la calidad.

Ninguno se equivoca del todo. «¿Leer esto cambiaría algo?» no tiene buena
respuesta para un ensayo que interesa, y la medición 25 ya mostró que el texto
no da para decidirlo de forma estable. Lo que sí es estable es una preferencia
de la persona: **a este autor lo leo, pero sin prisa.**

## La propuesta

Una lista nueva en el config, `filtros.remitentes_lectura` (dirección o
`@dominio`, con las mismas reglas de coincidencia que `remitentes_prioritarios`).
Un correo de esa lista sale en `READING_LATER`, como mínimo **y como máximo**,
salvo las excepciones de D2. El score no cambia: solo el tier, con un campo
`lectura_aplicada` (p. ej. `"REVIEW->READING_LATER (remitente de lectura)"`)
que el informe muestra.

Va en Python (`cmd_scoring`, junto al suelo de prioritarios) y lo decide el
script a partir del `remitente` del payload, como `prioritario` desde v3.21.27:
el modelo no puede aplicarlo ni saltárselo. Nace vacía: quien no la rellene
obtiene lo de siempre.

**Por qué no basta con lo que ya hay:**

- `suelo_prioritarios: READING_LATER` solo impide bajar, y ser prioritario
  suma +3, que sube un ensayo de 1-2 puntos a `REVIEW`. Agrava lo que se
  quiere arreglar.
- `remitentes_sin_penalizacion_masiva` solo quita los −4 de la regla B.
- `tier_maximo` existe, pero es del tope por inyección y lo pone el sanitizado,
  no el config.

## Decisiones para el mantenedor

**D1. ¿Suelo y techo, o solo techo?** Propuesta: los dos. Sin suelo, un
ensayo con veredictos duros volvería a `ARCHIVE` y saldría de «Leer Después».

**D2. ¿Qué rompe el techo?** Propuesta: `forzar_reply_needed` (F) y
`deadline_explicito_boost` (D); el tope por inyección siempre manda. La pregunta
directa (P) **no** lo rompe: en un boletín suele ser retórica («¿y tú qué
opinas?»). Si un autor de la lista escribe de verdad algo con plazo, D lo deja
subir.

**D3. ¿Suma puntos?** Propuesta: no. Los +3 de prioritarios tienen sentido para
personas; aquí solo cambia el tier.

**D4. ¿Y si un remitente está en las dos listas?** Propuesta: manda
`remitentes_lectura` (es la más específica) y `validar-config` avisa del
solape.

**D5. ¿Dominios genéricos?** Propuesta: `validar-config` avisa (sin rechazar) si
una entrada es un dominio de correo o de plataforma compartido (`@gmail.com`,
`@icloud.com`, `@outlook.com`, `@substack.com`…). Con un dominio así, todo
correo de esa plataforma quedaría fijo en `READING_LATER`.

**D6. ¿Cuenta como triaje?** Propuesta: sí, como el suelo de prioritarios. El
score y los vectores salen de los veredictos de siempre; solo el tier lo fija el
config, y queda escrito en `lectura_aplicada`. `registrar` no necesita
excepciones.

**D7. ¿Nombre?** Propuesta: `remitentes_lectura`. Alternativas:
`remitentes_leer_despues`, `remitentes_sin_prisa`.

## Qué no hace

- No aprende sola: la lista se escribe a mano. Es lo que la fase de historiales
  aparcada (`docs/diseno-historiales.md`) podría rellenar algún día a partir de
  lo que la persona conserva, pero eso queda fuera.
- No toca el scoring ni los 30 criterios, ni cambia nada a quien no la use.
- No mide si el evaluador acierta: es una regla de config, y se prueba con
  tests. El banco de boletines largos (`BANCO=lector` en
  `scripts/medir_evaluadores.py`) mide el evaluador sin ella.

## Cómo se probaría

1. Tests unitarios: techo y suelo, cada excepción de D2, el tope por inyección,
   la coincidencia por dirección y `+sufijo`, el solape de D4 y el aviso de D5.
2. Un dry-run real del mantenedor con 3-5 autores en la lista: los ensayos de
   esos autores en `READING_LATER` y el resto igual.
