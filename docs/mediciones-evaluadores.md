# Mediciones reales de los evaluadores LLM

Registro de las pruebas con proveedores reales y **correos inventados** (nunca
reales) en modo `hibrido`: cuántas filas llegan a propuesta y por qué vuelven
las demás al principal. Sirve para decidir qué tocar a continuación con datos,
no con impresiones.

Cómo medir (desde la raíz del repositorio clonado, con la clave cargada o, para
Apple, `fm serve` abierto; ver [`claves-api-macos.md`](claves-api-macos.md)):

```bash
PROVEEDOR=gemini python3 scripts/medir_evaluadores.py
PROVEEDOR=apple PAUSA=0 python3 scripts/medir_evaluadores.py
```

El script usa el `config.yaml` plantilla, no toca `~/.email-triage`, no lee el
buzón ni mueve nada. Solo imprime motivos, criterios, tiers y, por correo
inventado, las dudas, las evidencias vacías y el eco esperado frente al recibido.

**Ojo con las mediciones 1-5.** Hasta el PR que añadió este documento, el
script contaba dudas y `__no_aplica__` solo en las filas que pasaban el eco y la
validación (revisión de Codex): esos recuentos se quedan cortos en las filas
rechazadas, sobre todo en Apple, con 22 ecos fallidos. Los motivos por fila sí
son exactos. Desde entonces se cuentan sobre la respuesta capturada antes de
validarla.

**Tiers esperados (desde la medición 13).** Cada correo inventado tiene un tier
esperado y los controles que pondría el principal (pregunta directa, plazo,
remitente masivo, forzar `REPLY_NEEDED`), en `ESPERADOS` de
`scripts/correos_ficticios.py`. El script envía esos controles y cuenta los
aciertos de tier aparte en los 26 correos sin forzar: en los 14 forzados el
tier lo fija el control, no el evaluador. `CONTROLES=vacios` reproduce las
mediciones 1-12, que enviaban controles vacíos y por eso **no podían dar
ningún `REPLY_NEEDED`**: sin `forzar_reply_needed`, el scoring lo capa a
`REVIEW` (`cap_reply_needed_sin_accion`).

**Cómo leer los números.** Con 12 o 40 correos y modelos que no responden igual
en cada ejecución, las diferencias de 1-3 filas son ruido. Valen los órdenes de
magnitud y los patrones que se repiten. «Propuestas» suma `propuesta_validada` y
`reevaluar_tier_o_umbral` (esta última también llega al principal con
propuesta, para que la revise).

## Resumen

| Fecha | Proveedor | Versión | Correos | Propuestas | Freno principal |
|---|---|---|---|---|---|
| 2026-10-31 | Gemini `gemini-3.5-flash-lite` | 3.24.3 | 12 | 0 | `scoring_incompleto` (`__no_aplica__`) |
| 2026-10-31 | Gemini | 3.24.4 | 12 | 4 | dudas genéricas, evidencias vacías |
| 2026-10-31 | Gemini | 3.24.4 | 12 | 5 | dudas genéricas, evidencias vacías |
| 2026-10-31 | Gemini | 3.24.5 | 40 | **28** | `eco_distinto` (12) |
| 2026-11-01 | Apple `pcc` (`fm serve`) | 3.25.0 | 40 | 15 | `eco_distinto` (22) |
| 2026-11-01 | Apple `pcc`, recuento corregido | 3.25.0 | 40 | 14 | `eco_distinto` (21) |
| 2026-11-01 | Apple `pcc` | 3.25.1 | 40 | **22** | `eco_distinto` (16) |
| 2026-11-01 | Gemini | 3.25.1 | 40 | **34** | `eco_distinto` (6) |
| 2026-11-01 | Gemini | 3.27.1 | 40 | **35** | `eco_distinto` (5) |
| 2026-11-01 | Gemini, con controles y tiers esperados | 3.27.1 | 40 | 32 (aciertos 14 de 20 sin forzar) | `eco_distinto` (8) |
| 2026-11-01 | Gemini, eco de ocho palabras | 3.27.2 | 40 | 34 (aciertos 14 de 24 sin forzar) | `eco_distinto` (6) |
| 2026-11-01 | Ollama `qwen3.5` | 3.26.0 | 40 | 0 | `fallo_red_o_timeout` en el correo 2 |
| 2026-11-01 | Ollama `qwen3.5` | 3.26.2 | 40 | 3 | `evidencias_ausentes` (16) |

## Detalle y qué se cambió por cada una

### 1. Gemini, 12 correos, v3.24.3 — 0 de 12

`scoring_incompleto` 5, `evaluador_con_dudas` 5, `eco_distinto` 2. En las 10
filas evaluadas, los mismos 6 criterios no core salían `__no_aplica__`
(`true_rejection`, `privileging_the_hypothesis`, `proper_humility`,
`positive_bias`, `fake_justification`, `fake_optimization_criteria`): no es
juicio caso a caso, sino que esos criterios hablan de argumentos que una factura
no tiene. El freno descartaba filas cuya exclusión no cambiaba el score.

→ **v3.24.4**: un `__no_aplica__` en un no core con una sola opción a 0 puntos se
puntúa así si el score y el tier no cambian (`no_aplica_puntuado_como`).

### 2-3. Gemini, 12 correos, v3.24.4 — 4 y 5 de 12

`scoring_incompleto` desaparece. Quedan dudas (3-4), evidencias vacías (2-3) y
eco (1-2). Las dudas eran todas **datos ausentes que no cambiaban ningún
veredicto** («no se especifica a qué cuenta pertenece el aviso», «no se incluye el
importe exacto…»), porque el prompt decía «si falta información, anótalo en
dudas». Las evidencias vacías, criterios no core contestados «no» sin nada que
citar.

→ **v3.24.5**: el prompt pide dudas solo si impiden elegir y `__no_aplica__`
donde no hay nada que citar. La tolerancia de dudas sigue en 0.

### 4. Gemini, 40 correos, v3.24.5 — 28 de 40

`propuesta_validada` 19, `reevaluar_tier_o_umbral` 9, `eco_distinto` 12. **0
dudas y 0 evidencias vacías**: el cambio de prompt funcionó. Queda el eco.

### 5. Apple `pcc`, 40 correos, v3.25.0 — 15 de 40

`eco_distinto` 22, `reevaluar_tier_o_umbral` 10, `propuesta_validada` 5,
`evaluador_con_dudas` 3. Marca `__no_aplica__` en más criterios que Gemini (17
distintos) y sus 3 dudas vuelven a ser genéricas («sin datos verificables»):
sigue peor la instrucción de v3.24.5. Unos 13 s por correo; sin coste por token.

### 6. Apple `pcc`, 40 correos, v3.25.0, recuento corregido — 14 de 40

`eco_distinto` 21, `propuesta_validada` 8, `reevaluar_tier_o_umbral` 6,
`evaluador_con_dudas` 5. Con el recuento sobre la respuesta antes de validarla,
**11 filas de 40 traen dudas** (antes se veían 3), casi todas genéricas («¿Es la
universidad real?», «sin indicación clara de impacto»). Seis criterios salen
`__no_aplica__` en los 40 correos (`motivated_continuation`,
`motivated_stopping`, `retorno_atencional`, `confusion_productiva`,
`true_rejection`, `ruido_social`): no es juicio caso a caso.

El eco esperado frente al recibido resuelve la hipótesis: **dos causas**. Unos
11 empiezan por el asunto («Boletín de noviembre Novedades del mes:…») y unos 8
traen 2-3 palabras («Adjuntamos la factura» / «día 15.»), por debajo de las 4 de
6 que exige `eco_coincide`; un par mezclan los extremos.

→ **v3.25.1**: el prompt y el esquema piden el eco del campo `texto`, nunca del
asunto, con seis palabras exactas.

### 7. Apple `pcc`, 40 correos, v3.25.1 — 22 de 40

`eco_distinto` 16 (antes 21), `reevaluar_tier_o_umbral` 13,
`propuesta_validada` 9, `evaluador_con_dudas` 2; 4 filas con dudas (antes 11).
**Ningún eco empieza ya por el asunto.** Los 16 que quedan son cortos: 2-4
palabras por extremo («El formulario» / «al taller.»), y en dos el `fin` llega
vacío. Apple no cuenta palabras; precisar el campo no lo arregla. Los mismos
seis criterios siguen en `__no_aplica__` en los 40 correos.

### 8. Gemini, 40 correos, v3.25.1 — 34 de 40

`propuesta_validada` 21, `reevaluar_tier_o_umbral` 13, `eco_distinto` 6 (antes
12), 0 dudas. En los 6 ecos fallidos el `inicio` es correcto y el `fin` no son
las últimas palabras: se queda unas palabras antes del final («se renovará con
una subida» por «con una subida del 8 %.»).

→ **v3.27.1**: el prompt y la descripción de `eco.fin` piden que termine en la
última palabra del texto, con su puntuación. Medido en la 12.

### 12. Gemini, 40 correos, v3.27.1 — 35 de 40

`propuesta_validada` 22, `reevaluar_tier_o_umbral` 13, `eco_distinto` 5, 0
dudas. Los 5 fallos están en `fin`; los `inicio` traen 5-6 palabras y pasan (la
comprobación pide 4 de 6). El cambio hizo lo que pedía: en 4 de los 5 el `fin`
ya acaba en la última palabra del texto. Pero trae solo **3 palabras**
(«apuntarse al taller.», «hablarlo esta semana.»), y 3 no llegan a las 4
exigidas. El quinto devuelve las palabras finales desordenadas («hacer nada. No
tienes que» por «no tienes que hacer nada.»). Gemini no cuenta palabras: el
prompt ya dice «seis exactas» y entrega la mitad.

Los 13 `reevaluar_tier_o_umbral` no son un fallo del evaluador. Es el freno de
`evaluadores.py`: toda propuesta `ARCHIVE` o `REPLY_NEEDED`, o a 1 punto o menos
de una frontera, vuelve al principal. Aquí son las 12 `ARCHIVE` más una cerca de
un umbral. Otra cosa llama la atención: las 35 propuestas son `REVIEW` (23) o
`ARCHIVE` (12), sin `REPLY_NEEDED` ni `READING_LATER`, incluso en «¿Podemos
vernos el jueves?» o «Necesito el certificado de voluntariado». El script no
sabe qué tier *debería* tener cada correo inventado: mide cuántas filas pasan
los frenos, no si aciertan.

Revisado después: la ausencia de `REPLY_NEEDED` la causaba el propio script,
que enviaba los controles vacíos (sin `forzar_reply_needed`, el scoring capa
`REPLY_NEEDED` a `REVIEW`). La falta de `READING_LATER` no la explica el
control: ese tier depende solo del score.

→ Tiers esperados y controles por correo en `correos_ficticios.py`, y recuento
de aciertos en `medir_evaluadores.py`. Medido en la 13.

### 13. Gemini, 40 correos, v3.27.1, con controles — 32 de 40, 14 de 20 aciertos

Primera medición con los controles y tiers de `ESPERADOS`. `reevaluar_tier_o_umbral`
24, `propuesta_validada` 8, `eco_distinto` 8, 0 dudas. Tiers propuestos: 12
`REPLY_NEEDED`, 10 `REVIEW`, 9 `ARCHIVE` y 1 `READING_LATER`.

**Aciertos de tier.** 14 de 20 propuestas en los correos sin forzar (los que
miden al evaluador); 12 de 12 en los forzados, que no cuentan (el control fija
el tier). Los 6 fallos:

| Esperado → propuesto | Correos | Lectura |
|---|---|---|
| `READING_LATER` → `ARCHIVE` | 22 foto, 29 newsletter, 32 inauguración | Hipótesis de la medición 12 confirmada en 3 de 4 (el 10 acierta) |
| `ARCHIVE` → `REVIEW` | 12 notificación de envío, 39 confirmación de reserva | Sobrevalora avisos informativos |
| `REVIEW` → `ARCHIVE` | 5 contraseña cambiada | Probablemente pesa el −4 del control B, que es nuestro, no del evaluador |

El −4 de B también puede contribuir en el 29. En 22 y 32 no hay B: ahí el score
bajo es del evaluador.

**El eco** sube de 5 a 8 con el mismo prompt (los controles no lo afectan): el
orden de magnitud de la medición 12, con ruido. Los 8 fallan en `fin`, que trae
2-3 palabras, todas finales y en su orden salvo una. En el correo 26 el `fin`
acaba en «fin termina en la»: Gemini copió **nuestra instrucción** en el eco.

**Lo que deja `hibrido`.** Con controles realistas, `propuesta_validada` cae de
22 a 8: las propuestas `REPLY_NEEDED` y `ARCHIVE` vuelven al principal por
diseño. En la práctica, hoy `hibrido` solo propone por su cuenta filas `REVIEW`
y `READING_LATER`.

→ **v3.27.2**: el eco pide ocho palabras por extremo, con una instrucción más
corta que no empieza por «fin». `eco_coincide` sigue en 4 de 6; su tope de
longitud admite 2 palabras de más aunque sean fechas u horas. Pendiente de medir.
En `ESPERADOS`, el correo 5 (contraseña cambiada) pierde la B: un aviso de
seguridad no es correo masivo, y el −4 lo hundía a `ARCHIVE`. Medido en la 14.

### 14. Gemini, 40 correos, v3.27.2, eco de ocho palabras — 34 de 40, 14 de 24 aciertos

`reevaluar_tier_o_umbral` 25, `propuesta_validada` 9, `eco_distinto` 6, 0 dudas.

**El eco cambia de fallo, no de cifra.** Con seis palabras, Gemini daba 2-3 en
`fin`; con ocho, en 4 de los 6 fallos da **11-14** (correos 3, 18, 20 y 30:
«convenio con el ayuntamiento. ¿Te va el jueves a las 18?»), y el tope de
longitud lo rechaza. Los otros 2 siguen cortos (2-3 palabras). Gemini no cuenta
palabras: copia trozos de frase. En los 4 largos los extremos son correctos y
llegan hasta la última palabra.

**Aciertos de tier.** 14 de 24 sin forzar (10 de 10 forzados, que no cuentan):

| Esperado → propuesto | Correos | Lectura |
|---|---|---|
| `READING_LATER` → `ARCHIVE` | 10, 22, 29, 32 | 4 de 4; en la 13 fueron 3 de 4: patrón estable |
| `ARCHIVE` → `REVIEW` | 12, 36, 39 | Avisos informativos sobrevalorados; los tres salen `propuesta_validada` |
| `REVIEW` → `ARCHIVE` | 5, 35 | El 5 sigue en `ARCHIVE` **sin** la B: la hipótesis de la 13 era errónea, es del evaluador |
| `REVIEW` → `READING_LATER` | 21 | En la 13 acertó: variación entre ejecuciones |

De las 9 `propuesta_validada` (las que `hibrido` propone sin devolver al
principal), 3 tienen el tier equivocado (12, 36 y 39). Entre ejecuciones cambian
2-3 tiers del mismo correo, así que la cifra de aciertos tiene un ruido de unos
±3.

→ **v3.27.3** (opción A del mantenedor): `eco_coincide` mira el principio del
`inicio` y el final del `fin` (8 tokens), sin tope de longitud. Con los ecos de
esta medición, los 4 largos pasarían y los 2 cortos seguirían fallando.
Medido en la 15. Desde aquí `medir_evaluadores.py` imprime el score y los
ejes de cada propuesta y, en los fallos de tier, cuántos puntos la separan del
rango esperado: así se ve si los `READING_LATER` hundidos están a 1-2 puntos
(umbral) o muy lejos (veredictos).

### 15. Gemini, 40 correos, v3.27.3, eco por extremos — 40 de 40, 18 de 26 aciertos

`reevaluar_tier_o_umbral` 28, `propuesta_validada` 12, `eco_distinto` **0**, 0 dudas.

**El eco queda resuelto en esta medición.** Ningún fallo; se esperaban 2 (los
cortos de la 14), así que esta vez Gemini no los cortó. Es una sola ejecución:
el cambio deja pasar los largos, pero los cortos siguen dependiendo de la suerte.
Las 28 `reevaluar` son las 14 `REPLY_NEEDED` y las 12 `ARCHIVE`, que vuelven al
principal por diseño, más 2 cerca de la frontera.

**Aciertos de tier.** 18 de 26 sin forzar (14 de 14 forzados, que no cuentan).
Con el score a la vista, solo un fallo es de umbral:

| Esperado → propuesto | Correo: score (distancia) | Eje que lo mueve |
|---|---|---|
| `ARCHIVE` → `REVIEW` | 12: 9 (−10), 31: 16 (−17), 36: 11 (−12), 39: 16 (−17) | `valor_decisional` 8-10 en avisos de una línea |
| `READING_LATER` → `ARCHIVE` | 22: −3 (+3), 29: −16 (+16), 32: −14 (+14) | `calidad_epistemica` −3/−9/−10; en 29 y 32, también `riesgo_manipulacion` −3/−4 |
| `REVIEW` → `ARCHIVE` | 35: −6 (+10) | `calidad_epistemica` −6 y `riesgo_manipulacion` −4; la D (+4) no compensa |

**Lectura.** Solo el 22 está a 3 puntos de su rango. Los otros 7 fallan por
10-17 puntos: no se arreglan moviendo umbrales sino viendo qué veredictos los
empujan. Los ejes muestran dos patrones:

- **Avisos breves sobrevalorados.** Envío, factura duplicada, material
  olvidado y reserva confirmada sacan un `valor_decisional` de 8-10. Es el
  mismo patrón que en la 14 (12, 36 y 39 repiten). Dos de ellos (31 y 39) salen
  `propuesta_validada`: 2 de las 12 que `hibrido` propone por su cuenta tienen
  el tier equivocado. El 31 («ignorad la segunda») es discutible como
  `ARCHIVE`; tocar `ESPERADOS` es decisión del mantenedor.
- **Correo corto e informativo castigado.** Una newsletter, una invitación y una
  consulta pública pierden 6-14 puntos entre `calidad_epistemica` y
  `riesgo_manipulacion`. Hipótesis sin verificar: criterios pensados para
  textos con argumentos leen la falta de evidencia como mala calidad, en vez de
  como `__no_aplica__`. Para comprobarlo hace falta el desglose por criterio,
  que la medición aún no imprime.

Con una sola ejecución y un ruido de unos ±3 aciertos, la subida de 14 a 18 no
se puede atribuir a v3.27.3: también hay 2 filas más medibles, porque el eco ya
no rechaza ninguna.

→ En `ESPERADOS`, el correo 31 pasa a `REVIEW` (decisión del mantenedor): pide
no pagar dos veces. Desde aquí los fallos de tier muestran también los criterios
que puntúan, agrupados por eje, para comprobar la hipótesis del correo corto.
Medido en la 16.

### 16. Gemini, 40 correos, v3.27.3, criterios por eje — 39 de 40, 18 de 25 aciertos

`reevaluar_tier_o_umbral` 27, `propuesta_validada` 12, `eco_distinto` 1, 0 dudas.

**Eco.** Un fallo (correo 16): `fin` trae 3 palabras, «socios. Plazas
limitadas.». Es el fallo corto que ya se veía en la 14; el largo no ha vuelto.

**Aciertos de tier.** 18 de 25 sin forzar. El 31, ya como `REVIEW`, acierta y
sale validado. Los fallos son los mismos correos que en la 15, salvo el 31:

| Esperado → propuesto | Correo: score (distancia) |
|---|---|
| `ARCHIVE` → `REVIEW` | 12: 4 (−5), 36: 13 (−14), 39: 15 (−16) |
| `READING_LATER` → `ARCHIVE` | 22: −4 (+4), 29: −15 (+15), 32: −14 (+14) |
| `REVIEW` → `ARCHIVE` | 35: −5 (+9) |

**Correo corto e informativo (22, 29, 32, 35): no son veredictos absurdos, es la
aritmética.** Lo que muestra el desglose:

- `valor_decisional` suma **−12** en 22, 29 y 32, siempre con los mismos cuatro
  veredictos (`cambia_algo_concreto=no`, `cambio_predicciones=no`,
  `retorno_atencional=bajo`, `hug_the_query=tangencial`). Pero ese eje va de 0 a
  10 y el recorte lo deja en 0, así que no es lo que los hunde.
- Lo que resta es `calidad_epistemica` (−4 a −12, recortado a −10) y
  `riesgo_manipulacion` (−3/−4). Se repiten `sorpresa_bayesiana=baja` y
  `densidad_informativa=baja` en los cuatro, `cached_thought=enlatado` y
  `evidencia_filtrada=newsletter_marketing_burocratico` en tres, y
  `ruido_social=ritual` y `argument_screens_off_authority=solo_autoridad` en dos.
- Los veredictos son defendibles: una newsletter **es**
  `newsletter_marketing_burocratico`, que es una opción del propio criterio.
  La hipótesis de la 15 («leen la falta de evidencia como mala calidad») se
  cumple a medias: el evaluador aplica bien unos criterios que, por diseño,
  castigan este tipo de correo.

**Lo estructural** (verificado con los rangos de `ejes` del config, no con la
medición): `valor_decisional` y `presion_accion` no bajan de 0, y
`riesgo_manipulacion` y `coste_cognitivo` no suben de 0. En un correo sin valor
de decisión ni presión, el score es `calidad_epistemica` menos riesgo, menos
coste, más las reglas. Para llegar a `READING_LATER` (0 a 3) una newsletter con
la B (−4) y `evidencia_filtrada` (−3) necesita `calidad_epistemica` ≥ 7. Con
este config, `READING_LATER` para un correo corto agradable es casi
inalcanzable, lo evalúe quien lo evalúe.

**Avisos breves sobrevalorados (12, 36, 39).** `valor_decisional` suma +15/+22
(recortado a 10) con `cambia_algo_concreto=si`, `cambio_predicciones=si` y
`hug_the_query=directo`: Gemini cuenta como cambio una confirmación de lo que ya
se esperaba («tu reserva está confirmada»). Aquí el veredicto sí falla la
pregunta contrafáctica del criterio («¿leer esto cambiaría algo concreto que vaya
a hacer?»). El 12 baja a 4 (a 5 puntos) y el 36 y el 39 salen validados con el
tier equivocado: 2 de 12.

→ **v3.27.4**: el sistema de los evaluadores lleva `INSTRUCCION_CONTRAFACTICA`
(confirmar lo esperado no cambia nada; un dato que obligue o permita actuar de
otra forma, sí). Sin pesos ni umbrales nuevos. El correo corto informativo no
cambia con esto: es aritmética del config, pendiente de decisión del mantenedor.
Medido en la 17: el 5 (contraseña cambiada) y el 15 (cambio de horario) siguen
en `REVIEW`.

### 17. Gemini, 40 correos, v3.27.4, instrucción contrafáctica — 38 de 40, 19 de 26 aciertos

`reevaluar_tier_o_umbral` 25, `propuesta_validada` 13, `eco_distinto` 2, 0 dudas.

**Eco.** Dos fallos. En el 8, `fin` trae 3 palabras, el fallo corto de siempre.
En el 20, `fin` copia la penúltima frase («las horas que hice el verano
pasado.») y no la última: es un eco que no coincide de verdad, y el rechazo es
correcto.

**La instrucción contrafáctica, en 1 de 3.** El 39 (reserva confirmada) pasa a
`cambia_algo_concreto=no` y `cambio_predicciones=no`: `valor_decisional` baja de
+22 a −6 (recortado a 0) y el score de 15 a 0. Cae en `READING_LATER` y no en
`ARCHIVE`, porque el umbral de `READING_LATER` es 0 inclusive (ver abajo). El 12
(envío) y el 36 (material olvidado) siguen con `cambia_algo_concreto=si`, y
ahora los dos salen validados: 2 de las 13 `propuesta_validada` con el tier
equivocado, igual que en la 16. **No hay sobrecorrección**: el 5 (13) y el 15
(21) siguen en `REVIEW`. Con una sola ejecución, 1 de 3 no se distingue del
ruido.

**El correo corto, ahora a 2 puntos.** `READING_LATER` → `ARCHIVE` en 4 de 4:
10 (−2), 22 (−2), 32 (−5) y 29 (−17). El 10 y el 22 quedan a 2 puntos y caen
por un `calidad_epistemica` de −2. Se repiten `sorpresa_bayesiana=baja` y
`densidad_informativa=baja`.

**Lo estructural, visto en el 39.** Un correo con todos los ejes en 0 saca 0 y
cae en `READING_LATER`; uno con `calidad_epistemica` −2 saca −2 y cae en
`ARCHIVE`. Cuando `valor_decisional` y `presion_accion` quedan en 0 y tampoco
hay riesgo, coste ni reglas (el 39, el 10 y el 22), la frontera entre los dos
tiers la decide el signo de `calidad_epistemica`. En los demás también restan
el riesgo, el coste y las reglas (el 29: −3 de riesgo y −4 de la B), como en
la 16: con calidad +2 y riesgo −3 el score es −1 y el correo cae en `ARCHIVE`
(revisión de Codex, PR #179).

### Contraste con correos reales (2026-11-02): el umbral no es el problema

`scripts/distribucion_tiers.py` sobre los desgloses reales del mantenedor (21
sesiones, 1.058 correos, solo recuentos, sin texto):

| Tier | Correos |
|---|---|
| `REPLY_NEEDED` | 0 (0 %) |
| `REVIEW` | 380 (36 %) |
| `READING_LATER` | 203 (19 %) |
| `ARCHIVE` | 475 (45 %) |

| `ARCHIVE` por score | Correos | Con riesgo, coste o reglas |
|---|---|---|
| −2 o más | 62 | 58 |
| −5 a −2 (sin el −2) | 108 | 93 |
| −10 a −5 (sin el −5) | 127 | 127 |
| menos de −10 | 178 | 178 |

Con umbral −1 pasarían a `READING_LATER` 27 correos; con −2, 62; con −3, 92, y
con −5, 170.

**Lectura.**

- **`READING_LATER` no está vacío con correo real: un 19 %.** La conclusión de
  las mediciones 16 y 17 («casi inalcanzable para un correo corto») vale para
  los 40 correos ficticios, de una sola línea, no para el buzón real. Era un
  sesgo del banco de pruebas. *Corregido en la 18: con correos largos falla
  igual; ver allí los tres factores que confunden la comparación.*
- **Los `ARCHIVE` cerca del umbral casi siempre tienen otras penalizaciones**:
  58 de 62 en el tramo de −2 o más, y 93 de 108 en el siguiente. Bajar el
  umbral rescataría sobre todo correo masivo o con riesgo, no correo corto
  agradable. Con −5, `READING_LATER` casi se duplicaría (de 203 a 373).
- **No se toca el umbral de la plantilla.** Lo que había que corregir era el
  banco de pruebas: de ahí los 40 correos nuevos de la medición 18.
- **Los 1.058 no son el correo diario del mantenedor** (aclarado por él,
  2026-11-02). La mayoría pasa antes a mano a «Leer Después», una carpeta que
  usa como almacén de pruebas; los resultados («ARCHIVE-TRIAGE», «Urgentes
  Claude») se reutilizan a veces, así que hay correos repetidos entre
  sesiones; y lo importante de verdad («Archivados») nunca entra en el
  triaje. Las cifras describen esa población preseleccionada y reutilizada,
  no un buzón típico: no sirven para fijar umbrales ni proporciones de tier.
- **`REPLY_NEEDED`: 0 de 1.058.** Sin `forzar_reply_needed`, el scoring capa
  `REPLY_NEEDED` a `REVIEW` (`cap_reply_needed_sin_accion`). Que ningún correo
  real lo haya alcanzado sugiere que el principal no está marcando la F en el
  triaje real. Pendiente de investigar; es otro asunto.

### 18. Gemini, 80 correos, v3.27.4 — 77 de 80, 42 de 57 aciertos

El banco de 80 correos se describe al final de esta sección.

`reevaluar_tier_o_umbral` 56, `propuesta_validada` 21, `eco_distinto` 3, 0
dudas. Aciertos sin forzar: 17 de 25 en los correos 1-40 y 25 de 32 en los
41-80 (20 de 20 forzados).

**Eco.** Tres fallos (16, 53 y 75), los tres el mismo: `fin` con 3 palabras.
Es el único fallo de eco que queda, en un 3-4 % de los correos.

**Avisos: la distinción contrafáctica funciona con texto real.** Las 6
confirmaciones (41-46) salen `ARCHIVE` y los 4 avisos que piden algo (47-50)
salen `REVIEW`, los 4 validados. El 39 (reserva) acierta otra vez. Siguen
fallando el 12 (envío) y el 36 (material olvidado), los dos de una línea, y
aparece una **sobrecorrección**: el 5 (contraseña cambiada) da
`cambia_algo_concreto=no` y cae a `READING_LATER` con score 0, cuando en la 17
sacó 13. Su gemelo largo, el 49 (inicio de sesión raro), acierta con 27. Es
una sola ejecución, pero conviene vigilarlo.

**`READING_LATER`: 2 de 13, también con correos largos.** Fallan 10 de 13, casi
todos hacia `ARCHIVE`, y los nuevos (51, 52, 60, 61, 63 y 79) fallan igual que
los viejos: **no era el largo del correo.** El desglose repite los mismos
criterios: `ruido_social=ritual` (−3, en 7 de los 10), `sorpresa_bayesiana=baja`,
`densidad_informativa=baja` y `forward_backward_flow=backward`, más
`evidencia_filtrada=newsletter_marketing_burocratico` y la B en los boletines.
Gemini aplica los criterios tal como están escritos: un agradecimiento o una
felicitación **son** ritual social y no cambian ninguna decisión.

**Por qué no cuadra con el 19 % real.** La comparación con los 1.058 correos
reales mezcla tres cosas distintas:

1. **Evaluador.** En el triaje real evalúa Claude como principal; aquí evalúa
   Gemini. Puede ser cosa de Gemini.
2. **Población.** El mantenedor pasa a mano la mayoría de correos a «Leer
   Después» y hace el triaje desde ahí. El correo real ya llega preseleccionado,
   y probablemente eso explica también los 0 `REPLY_NEEDED`: lo que pide
   respuesta se atiende en la bandeja de entrada.
3. **Expectativa.** Con la pregunta del plugin («¿leer esto cambiaría algo?»),
   una felicitación en `ARCHIVE` es coherente. Que deba ir a `READING_LATER`
   es una decisión de diseño, no un error del evaluador.

*Decidido después (2026-11-02):* el mantenedor fija la expectativa en
`ARCHIVE` para los cinco correos sociales sin nada que hacer (22 y 60-63). Las
mediciones 1-18 se puntuaron con `READING_LATER`; desde la 19, los aciertos se
cuentan con la expectativa nueva y no son comparables uno a uno. Hay que
**vigilar el 5** (contraseña cambiada): si en la 19 vuelve a `READING_LATER`,
la sobrecorrección de la instrucción contrafáctica deja de ser anecdótica.

### 19. Gemini, 80 correos, v3.27.4, sociales a `ARCHIVE` — 75 de 80, 42 de 55 aciertos

Primera con la expectativa nueva (sociales 22 y 60-63 en `ARCHIVE`), así que
no es comparable uno a uno con la 18: al menos tres aciertos más (60, 61 y 63
caían a `ARCHIVE` en la 18) vienen de cambiar la regla, no de un evaluador
mejor. `reevaluar_tier_o_umbral` 55, `propuesta_validada` 20, `eco_distinto` 5,
0 dudas. Aciertos sin forzar: 17 de 25 en 1-40 y 25 de 30 en 41-80 (20 de 20
forzados).

**Eco.** Cinco fallos (16, 53, 63, 75 y 79). Cuatro son el `fin` corto de
siempre. El 63 es nuevo: Gemini mezcla dos trozos del texto («cerámica. Aquí he
encontrado un abrazo todos.»), y el freno lo caza, que es para lo que está.

**Sociales.** 22, 60 y 61 aciertan (`ARCHIVE`); el 62 (crónica) sale
`READING_LATER` con score 2 y el 63 falla el eco.

**El correo 5 repite la sobrecorrección.** Otra vez `READING_LATER` con score 0
y el mismo desglose (`cambia_algo_concreto=no` −5, `cambio_predicciones=no`
−3): lee el aviso como confirmación de algo pedido, que es lo que dice
`INSTRUCCION_CONTRAFACTICA`, cuando en un aviso de seguridad no se sabe si lo
pidió el destinatario. Su gemelo, el 49, acierta con 5, a un punto del límite
de `REVIEW`. Dos ejecuciones seguidas: deja de ser anecdótico. Siguen fallando
el 12 y el 36 (avisos de una línea a `REVIEW`).

**`READING_LATER`: 0 de 7.** Seis a `ARCHIVE` y uno (56) a `REVIEW`. El
desglose muestra una causa aritmética, no del evaluador: el recorte de
`valor_decisional` anula los criterios de interés y tres penalizaciones miden
lo mismo en los boletines. Diagnóstico completo en
[`auditoria-reading-later.md`](auditoria-reading-later.md).

### 20. Gemini, 120 correos, v3.27.4, sin cambios — 114 de 120, 67 de 84 aciertos

Punto de partida antes de tocar el correo 5: mismo plugin que la 19 y 40
correos nuevos. `reevaluar_tier_o_umbral` 83, `propuesta_validada` 31,
`eco_distinto` 5, `evidencias_ausentes` 1 (el 23), 0 dudas. Aciertos sin
forzar: 18 de 24 en 1-40, 28 de 32 en 41-80 y 21 de 28 en 81-120 (30 de 30
forzados).

**El 5 acierta sin haber tocado nada: `REVIEW` con 27.** En la 18 y la 19 sacó
0. El mismo correo salta 27 puntos de una ejecución a otra: el veredicto de
`cambia_algo_concreto` es bimodal (sí +5 / no −5) y arrastra a los demás. **Una
ejecución no basta para decir si un arreglo funciona**: de ahí `IDS` y
`REPETIR` en `medir_evaluadores.py`, para medir varias veces solo los correos
que importan.

**Avisos de seguridad nuevos (81-84): 3 de 4.** 81, 82 y 83 dan `REVIEW` con
27. El 84 («hemos recibido una solicitud para restablecer tu contraseña… si
no la has pedido…») cae a `READING_LATER` con 0, con el desglose idéntico al
del 5 en la 18 y la 19: lo lee como confirmación de algo pedido. La
sobrecorrección existe y no es del 5: aparece cuando el aviso está redactado
como acuse de una petición.

**`READING_LATER`: 4 de 17**, y el reparto confirma la auditoría
([`auditoria-reading-later.md`](auditoria-reading-later.md)):

- **Con B (remitente masivo): 0 de 8** (29, 51, 52, 53, 86, 87, 88 y 91), de
  −2 a −18. Los boletines afines nuevos (86, 87) se hunden igual que los
  viejos, con la misma triple penalización.
- **Sin B: 4 de 9** (59, 79, 90 y 93 aciertan, con 1-2 puntos). Las
  recomendaciones personales pueden llegar; el 89 se queda en −1 y el 10 en −3.
- El 92 (puertas abiertas) y el 56 (presentación) salen `REVIEW` con 22 y 11:
  Gemini los lee como una opción que tomar. La expectativa es discutible.

**Otros.** El 12 acierta por primera vez (`ARCHIVE`, −4). Siguen fallando el
21 (reglamento, `READING_LATER` con 1), el 35 (encuesta municipal, `ARCHIVE`) y
el 36 (material olvidado, `REVIEW`). El eco falla 5 veces: cuatro por el `fin`
corto de siempre y el 85 por un `fin` tomado de la mitad del texto.

### 21. Gemini, avisos de seguridad repetidos, v3.27.4 — punto de partida

`IDS=5,49,81-84 REPETIR=5` (30 evaluaciones), antes de tocar la instrucción.
Por correo, tier esperado `REVIEW`:

| Correo | Aciertos | Pasadas |
|---|---|---|
| 5 contraseña cambiada | 1 de 5 | `ARCHIVE` −3, `REVIEW` 27, `ARCHIVE` −9, −7, −5 |
| 49 inicio de sesión nuevo | 3 de 5 | `REVIEW` 27 ×3, sin propuesta, `ARCHIVE` −5 |
| 81 correo de recuperación | 5 de 5 | `REVIEW` 24-27 |
| 82 dos pasos desactivada | 5 de 5 | `REVIEW` 27 |
| 83 teléfono nuevo en el banco | 3 de 5 | `REVIEW` 24-27, 2 sin propuesta |
| 84 restablecer contraseña | 1 de 5 | `REVIEW` 27, 4 sin propuesta |

De las 23 propuestas, **5 fallan, todas hacia `ARCHIVE`**, y todas con el
mismo desglose: `cambia_algo_concreto=no` y `cambio_predicciones=no`. El 5
falla 4 de 5, peor que en la 18-20: no era una mala racha. Los 81 y 82, que
dicen el riesgo de forma explícita («tu cuenta es ahora más vulnerable»),
aciertan siempre; fallan los que se parecen a un acuse («se ha cambiado»,
«hemos recibido una solicitud»).

**El 84 no se puede juzgar todavía:** 4 de 5 pasadas sin propuesta por
`eco_distinto`, el `fin` corto de siempre («intentando entrar.»). Es el
problema de eco que queda, no el de la instrucción.

En v3.27.5 la instrucción contrafáctica añade que un aviso de cambio o de
acceso a una cuenta no es una confirmación si el correo no muestra que lo hizo
el destinatario. La medición de después debe repetir exactamente este comando
y, aparte, una completa de 120 para ver si mueve otros correos (sobre todo las
confirmaciones 41-46 y 97-99, que deben seguir en `ARCHIVE`).

### El banco de 80 correos

`correos_ficticios.py` pasa de 40 a 80. Los 40 primeros no cambian, así que
con `N=40` se pueden comparar con las mediciones 1-17. Los 40 nuevos (41-80)
tienen cuerpos de 2-4 frases y se cargan hacia los casos dudosos:

- 6 avisos que confirman lo esperado (`ARCHIVE`) frente a 4 avisos que piden
  algo (`REVIEW`);
- 3 boletines afines (`READING_LATER`) frente a 2 ajenos (`ARCHIVE`);
- 2 invitaciones sin compromiso y 4 correos sociales (`READING_LATER`) frente
  a 1 invitación con plazo (`REVIEW`) y 1 feria comercial (`ARCHIVE`);
- 6 `REPLY_NEEDED` con pregunta directa, y 5 de spam o phishing, más un cierre
  de hilo, en `ARCHIVE`.

En total: 14 `ARCHIVE`, 10 `REVIEW`, 10 `READING_LATER` y 6 `REPLY_NEEDED`.
Desde el 2026-11-02, con los sociales (22 y 60-63) en `ARCHIVE`, el banco
completo queda en 30 `ARCHIVE`, 21 `REVIEW`, 9 `READING_LATER` y 20
`REPLY_NEEDED`.

Desde la medición 20 el banco tiene **120 correos** (tres bloques de 40;
`N=80` repite la 18 y la 19). Los 40 nuevos (81-120): 4 avisos de seguridad
que el destinatario pudo no provocar (`REVIEW`, no vistos antes de tocar el
correo 5), 1 recordatorio de privacidad sin cambios y 8 promociones,
confirmaciones y sociales (`ARCHIVE`), 8 materiales afines sin nada que hacer
(`READING_LATER`), 9 avisos o decisiones (`REVIEW`) y 10 respuestas
pendientes (`REPLY_NEEDED`). El banco completo: 39 `ARCHIVE`, 34 `REVIEW`, 17
`READING_LATER` y 30 `REPLY_NEEDED`. Los tiers de 81-120 son un borrador que
tiene que aceptar el mantenedor.
Los tiers esperados de 41-80 son un borrador que tiene que aceptar el
mantenedor. Como el núcleo admite como mucho 50 correos por lote
(`MAX_LOTE`, un freno que no se toca), `medir_evaluadores.py` mide en dos
lotes de 40 y da los aciertos también por bloque.




### 9. Ollama `qwen3.5`, 40 correos, v3.26.0 — 0 de 40 (lote detenido)

El correo 1 llegó con eco distinto (copiado del asunto); el 2 tardó más de 300 s
(`fallo_red_o_timeout`) y detuvo los 38 restantes. Una segunda ejecución
inmediata falló ya en el correo 1. Contexto comprobado después con `ollama ps`:
16.384, así que no fue un recorte. Causa probable: sin tope de salida, el modelo
siguió generando, y Ollama no abandona la respuesta cuando el cliente deja de
esperar, de modo que la siguiente petición quedó en cola.

→ **v3.26.2**: `max_tokens` = 3.450 (el margen del preflight de v3.26.1).

### 10. Ollama `qwen3.5`, 40 correos, v3.26.2 — 3 de 40

**Los 40 correos llegan al final**: el tope de salida resolvió los bloqueos. La
calidad, no: `evidencias_ausentes` 16, `respuesta_incompleta` 9 (llega al tope
de 3.450; en la sonda gastó 1.900-2.300), `eco_distinto` 8,
`reevaluar_tier_o_umbral` 3, `ids_inesperados` 2 y
`criterio_core_omitido_o_sin_justificacion` 2. Deja vacías las evidencias de
decenas de criterios en vez de usar `__no_aplica__` (no sigue la instrucción de
v3.24.5), inventa texto en el eco («peligro y fraude ocultos en la
solicitud», «renewamos») y sus dudas se salen del tema. Los frenos paran
alucinaciones reales: relajarlos metería ruido en el triaje.

Conclusión: con 16 GB, `qwen3.5` (7,6 GB en memoria) no sirve para `hibrido`.
Queda como opción experimental para probar en local. Pendiente: saber si las
respuestas cortadas son razonamiento oculto pese a `reasoning_effort: none` o
pura verbosidad; desde esta medición `medir_evaluadores.py` imprime los tokens
de salida y el tiempo de cada correo.

### 11. Modelos de decisión locales, 12 correos, tres variantes — 0 de 12

`scripts/sonda_decision_local.py` (2026-11-01). Freno de `hibrido`: 0 inciertos
y confianza de al menos 0,8 en los 30 criterios.

| Modelo · variante | s/correo | Inciertos (med.) | `__no_aplica__` (med.) | Conf. mín. (med.) | Conf. mediana | Pasan |
|---|---|---|---|---|---|---|
| `tev1:4b` · es | 15,6 | 13 | 5,5 | 0,005 | 0,109 | 0 |
| `tev1:4b` · es sin incierto | 12,2 | 0 | 14 | 0,004 | 0,100 | 0 |
| `tev1:4b` · en sin incierto | 12,1 | 0 | 15 | 0,001 | 0,120 | 0 |
| `d1` · es | 3,8 | 3 | 13 | 0,184 | 0,459 | 0 |
| `d1` · es sin incierto | 3,3 | 0 | 15 | 0,213 | 0,570 | 0 |
| `d1` · en sin incierto | 3,1 | 0 | 15 | 0,139 | 0,462 | 0 |

Quitar `__incierto__` no aporta seguridad: los inciertos pasan a
`__no_aplica__` (de 5,5 a 14-15 en `tev1:4b`) y la confianza apenas cambia. El
inglés no ayuda. `d1` sin incierto es lo más prometedor (mediana 0,57; en
`semantic_stopsigns`, 12 de 12 por encima de 0,8), pero ninguna fila llega al
umbral en los 30 criterios a la vez.

→ **v3.27.0**: adaptador `decision_local` con las preguntas de siempre (con
`__incierto__`), a petición del mantenedor. Útil para `comparar`; en `hibrido`
todo vuelve al principal. El freno no se relaja.

## Sondas de contrato (antes de escribir un adaptador)

- **Apple `fm serve`** (`scripts/sonda_fm.py`, 2026-11-01): `system` (on-device)
  tiene 4.096 tokens de contexto en total y nuestra petición ocupa unos 4.090 de
  entrada más ~1.400 de salida: no cabe. `pcc` acepta `response_format`
  `json_schema` estricto. `fm serve` responde en streaming salvo `stream: false`.
- **Ollama 0.40.13** (`scripts/sonda_ollama.py`, 2026-11-01, MacBook Pro de
  16 GB, `OLLAMA_CONTEXT_LENGTH=16384 ollama serve`; con menos de 24 GB Ollama
  usa 4.096 tokens por defecto). Un correo ficticio, dos ejecuciones:
  - `qwen3.5` por Chat Completions: cumple el esquema estricto, 0 dudas, 4.144
    tokens de entrada y 1.900-2.300 de salida (más que Apple: puede que siga
    razonando con `reasoning_effort: none`), **105-119 s por correo**. Eco
    incorrecto, como Apple.
  - Modelos de decisión por `/v1/systemone` (mismo contrato que Jev, respuesta
    válida): `tev1:4b` elige `__incierto__` en 25 de 30 criterios (confianza
    mediana 0,13); `d1`, 7 inciertos y 13 `__no_aplica__` (mediana 0,24). En
    `hibrido` ninguno daría propuesta: antes de un adaptador, probar sin
    `__incierto__` y con instrucciones en inglés.

## El eco

Era el freno principal en los dos proveedores (30 % en Gemini, 55 % en Apple).
La medición 6 confirmó la hipótesis del asunto y encontró una segunda causa, los
ecos cortos; v3.25.1 precisa el prompt sin relajar la comprobación. Efecto
medido: Gemini pasa de 12 a 6 ecos fallidos y Apple de 21 a 16, y el asunto
desaparece en los dos. Lo que queda es distinto en cada uno: Apple devuelve
extremos cortos; Gemini, un `fin` que no llega al final. Ninguno de los dos se
arregla nombrando el campo. v3.27.1 consiguió que el `fin` de Gemini acabe en su
sitio (medición 12), pero sigue corto: 3 palabras en vez de 6. Por prompt queda
poco que ganar. En `qwen3.5` el eco es solo uno de sus problemas (medición 10).

---

> Elaborado con asistencia de IA; requiere revisión humana.
