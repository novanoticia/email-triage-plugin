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
Pendiente de medir.




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
