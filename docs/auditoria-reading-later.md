# Auditoría: por qué `READING_LATER` casi no se alcanza

Estado: **la opción 1 se aplicó en v3.27.6 y se midió** (medición 24:
`READING_LATER` de 3 a 6 de 17, todos sin B; con B, 0 de 8). Ver «Tras la
medición 24» al final. Redactada el 2026-11-02 tras las
mediciones 18 y 19 (`docs/mediciones-evaluadores.md`). Cualquier cambio de
pesos, rangos o redacción de criterios que salga de aquí toca el scoring: va
en un PR propio, con tests, y nace sin cambiar nada a quien no toque su config
(regla de `CLAUDE.md`).

## Los síntomas

- **Medición 18:** 2 de 13 correos que esperaban `READING_LATER` lo
  alcanzaron; los otros caen casi todos a `ARCHIVE`.
- **Medición 19:** 0 de los 7 que se pudieron medir (otros 2 fallaron el eco).
  Seis caen a `ARCHIVE` y uno a `REVIEW`.
- No es el largo del correo (los de 2-4 frases fallan igual que los de una
  línea) ni el umbral (con los 1.058 correos reales, bajar el umbral rescataría
  sobre todo correo masivo o con riesgo).

El plugin define `READING_LATER` como «interesante pero no urgente» (score 0 a
3). La pregunta es si el scoring puede expresar «interesante».

## Primer hallazgo: el recorte de `valor_decisional` anula los criterios de interés

`valor_decisional` se recorta a `[0, 10]` (`scoring.ejes` del config). Un correo
sin nada que hacer recibe en ese eje, de forma casi fija:

| Criterio | Veredicto | Puntos |
|---|---|---|
| `cambia_algo_concreto` | no | −5 |
| `cambio_predicciones` | no | −3 |
| `retorno_atencional` | bajo | −2 |
| `hug_the_query` | tangencial | −2 |
| **suma** | | **−12** |

Los dos criterios que miden algo parecido a «interesante» están en el mismo
eje: `relevancia_longitudinal` («¿Mi yo de dentro de un mes agradecerá haber
leído esto?», `si` +4) y `abre_opciones` (+3). Aunque los dos den su máximo, la
suma queda en −5 y el recorte la deja en **0**. **Para un correo sin acción,
esos dos criterios no pueden cambiar nunca el resultado.** No es un fallo del
evaluador: es aritmética.

Que el recorte exista tiene sentido: «no cambia nada» no debería restar más que
cero en el eje de la decisión. Pero pone a los criterios de interés en el sitio
donde no pueden actuar.

## Segundo hallazgo: tres penalizaciones miden lo mismo en un boletín

Con `valor_decisional` en 0, el tier lo decide `calidad_epistemica` más el
riesgo y las reglas. Un boletín afín (correos 29, 51 y 52) recibe:

| Penalización | Eje | Puntos | Qué pregunta |
|---|---|---|---|
| `ruido_social=ritual` | calidad | −3 | «¿Es señal real o ritual social/**burocrático**?» |
| `evidencia_filtrada=newsletter_marketing_burocratico` | riesgo | −3 | «¿Cuál es el algoritmo del remitente?» |
| `sender_bulk_penalizacion` (B) | reglas | −4 | remitente masivo |

Las tres responden a lo mismo: «esto lo manda una máquina a mucha gente». Juntas
son −10, y además suelen venir `sorpresa_bayesiana=baja` (−2),
`densidad_informativa=baja` (−2) y `cached_thought=enlatado` (−2). El correo 29
(boletín afín) suma −15.

La redacción de `ruido_social` lo agrava: la palabra «burocrático» lo extiende a
cualquier boletín o normativa. En la medición 19 Gemini lo aplica a un
reglamento de protección de datos (21), a una encuesta municipal (35), a un
concierto de vecinos (59) y a los boletines afines. Aplica el texto tal como
está escrito; el texto dice más de lo que quería decir, que era el ritual
*social* (cortesías, felicitaciones, «gracias a todos»).

## Lo que no es el problema

- **La B por sí sola.** La fase 3 de `docs/diseno-historiales.md` (aparcada)
  atenuaría la B de −4 a −1 para remitentes conservados; el 29 seguiría en −12.
- **El umbral.** Ya descartado con los correos reales.
- **El evaluador.** Gemini es coherente con los criterios: un boletín *es*
  marketing y *no* cambia una decisión. Con Claude como principal habría que
  medirlo, pero la aritmética del primer hallazgo vale para cualquier
  evaluador.

## Opciones (la 1 aplicada en v3.27.6)

Ordenadas de menor a mayor alcance. Todas son cambios del scoring.

1. **Acotar `ruido_social` a lo social.** Quitar «burocrático» de la pregunta
   (la burocracia ya la cubre `evidencia_filtrada`). Es solo redacción: no
   cambia pesos ni rangos, pero cambia veredictos y hay que medirlo. Riesgo
   bajo; quita una de las tres penalizaciones duplicadas en boletines y
   normativas.
2. **Sacar los criterios de interés del eje recortado.** Mover
   `relevancia_longitudinal` (y quizá `abre_opciones`) a `calidad_epistemica`,
   que admite negativos y no se queda en 0. Cambia el `eje` de un criterio
   (exige `validar-config`, tests y catálogo) y su significado: «valor para
   leer» frente a «valor para decidir».
3. **Un criterio nuevo de afinidad con el perfil** («¿encaja con los intereses
   declarados del destinatario?»). Rompe los 30 criterios exactos (gate #2):
   exige auditar el catálogo entero antes, como pide `CLAUDE.md`. Es lo más
   limpio conceptualmente y lo más caro.
4. **No tocar el scoring y aceptar que `READING_LATER` llega por config**
   (remitentes prioritarios con suelo `READING_LATER`, que ya existe). Es
   coherente con la pregunta del plugin, pero entonces la descripción del tier
   («interesante pero no urgente») promete algo que el modelo no puede decidir.

**Recomendación:** la 1 ya, porque es pequeña y corrige una redacción que se
aplica mal. La 2, medida aparte, después de la 1, para saber cuánto arregla
cada una. La 3 solo si la 1 y la 2 no bastan. Antes de cualquiera de ellas, el
arreglo del correo 5 (paso 3 del plan), que toca el prompt y conviene medir
aislado.

## Cómo medirlo

Con el banco de 120 correos (17 esperan `READING_LATER`, 8 de ellos nuevos,
81-120): una medición antes del cambio y otra después, mismo proveedor. El
dato que importa es cuántos `READING_LATER` esperados se alcanzan sin que
suban los falsos `READING_LATER` en los `ARCHIVE` (promociones, sociales).

## Tras la medición 24

- **La opción 1 cumplió:** `ruido_social` desaparece de los boletines y
  `READING_LATER` pasa de 3 a 6 de 17 sin falsos positivos de publicidad.
- **La opción 2 no merece la pena todavía.** Simulada sobre los fallos,
  rescata 2 (88 y 93) y aleja otros 2 (56 y 92, a `REVIEW` con 9 y 12). El
  balance real depende de los aciertos, cuyo desglose la medición no imprime.
- **El resto es de remitente, no de texto.** Los ocho fallos con B quedan a
  4-18 puntos y Gemini los evalúa igual que una promoción. Eximir la B
  (`remitentes_sin_penalizacion_masiva`) solo suma 4: el 29 seguiría en −9.
  Lo que sí los lleva a `READING_LATER` es el suelo de prioritarios
  (`suelo_prioritarios`), que ya existe y es por remitente: es la opción 4, y
  el sitio natural donde encajaría la fase de historiales aparcada
  (`docs/diseno-historiales.md`).

**Siguiente paso:** `GUARDAR=RUTA` en `medir_evaluadores.py` guarda los
veredictos de una pasada (solo de los correos inventados, sin texto) y
`scripts/simular_scoring.py RUTA` los vuelve a puntuar con las variantes 2a
(solo `relevancia_longitudinal`) y 2b (también `abre_opciones`), o con
cualquier `--eje`/`--rango`, sin llamar al proveedor. Pendiente: una medición
con `GUARDAR` para simular la opción 2 con todos los correos.
