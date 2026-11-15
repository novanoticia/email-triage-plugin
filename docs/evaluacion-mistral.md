# Evaluación del revisor de Mistral con casos reales

Los tests del revisor fijan su mecánica (qué se envía, qué se valida, qué se
publica). No dicen si el modelo **encuentra defectos de verdad**. Esta
evaluación sí, con commits del propio historial: es la propuesta 2 de la
[auditoría del 29 de octubre de 2026](auditoria-mistral-2026-10-29.md).

Estado: **herramienta lista, sin resultados todavía**. Ninguna cifra de este
documento procede de una ejecución real.

## Qué mide

Cada caso de `.github/eval/casos.json` fija dos commits y se revisa con el
mismo código que un PR (diff, contexto, prompt, llamada y validación de
`mistral_review.py`).

| Tipo | Qué es | Qué se cuenta |
|---|---|---|
| **positivo** | `cabeza` tiene un defecto conocido; `arreglo` es el commit que lo corrigió. | Si algún hallazgo cita una línea dentro de una función que el arreglo tocó («señala la función»). |
| **negativo** | Sobre `cabeza`, Mistral publicó hallazgos que la auditoría contrastó como falsos. | Cuántos hallazgos hay y cuántos caen otra vez en los mismos archivos. |

El objetivo de un positivo no se escribe a mano: se deriva del diff entre la
cabeza y el arreglo (funciones Python que no son tests). `ignorar` excluye
archivos que el arreglo tocó sin ser el defecto.

Hoy hay 7 positivos (#123, #125, #126, #143, #199 y dos de #200) y 5
negativos (#108, #114, #116, #123, #140), más un **caso de control**
(`c1-guarda-invertida`, con `"control": true`).

El control es un defecto sintético y evidente: `_porcentaje` en
`scripts/distribucion_tiers.py` con la guarda invertida, que se ve entero en
un diff de pocas líneas. Su defecto y su arreglo son dos commits seguidos del
mismo PR, así que en `main` solo queda la versión correcta. Sirve para separar
dos lecturas de un 0 de 7: si un modelo tampoco ve el control, no ve defectos
evidentes; si lo ve y falla los reales, los casos reales piden algo que el
revisor no recibe (contexto de otros archivos, conocer el proyecto). No cuenta
entre los 7: los resultados se comparan aparte.

## Lo que no mide

- **Señalar la función no prueba acertar.** Un hallazgo puede caer en la
  función correcta y describir otra cosa. El informe lista cada hallazgo para
  que una persona lo etiquete; solo esa etiqueta es el resultado.
- **No señalarla sí es informativo:** el defecto no se vio.
- En los negativos, un hallazgo nuevo en el mismo archivo no es
  automáticamente falso: hay que leerlo.
- Doce casos y pocas repeticiones dan una impresión con números, no una
  estadística. No sirven para comparar diferencias pequeñas.
- Los casos proceden de este repositorio y los positivos los encontraron
  otros revisores (Codex, pruebas reales): es una muestra sesgada hacia lo que
  otros sí vieron.

## Diferencias con una revisión real

- El título es el asunto del commit y **no hay descripción**: la del PR
  histórico podía nombrar el arreglo.
- La guía (`CLAUDE.md`) es la del árbol actual, no la de entonces.
- El diff es el del PR hasta ese commit (`base...cabeza`), como en una
  revisión a mitad de PR.

## Cómo ejecutarla

**Actions → Mistral Eval → Run workflow.** Cuatro campos:

- `repeticiones`: revisiones por caso (2 por defecto).
- `solo`: ids separados por comas; vacío evalúa todos.
- `modelo`: un modelo solo para esta evaluación (por ejemplo
  `mistral-large-2512` o `codestral-latest`). Vacío usa `MISTRAL_MODEL`. El
  revisor de los PR no cambia: sirve para comparar modelos sin tocarlo.
- `esfuerzo`: esfuerzo de razonamiento (`low`, `medium`, `high`) solo para
  esta evaluación. Vacío usa el del revisor. Si el modelo no lo admite, se
  retira solo y el informe lo dice.
- `max_salida`: tope de tokens de salida por respuesta (`max_tokens`), de
  4.000 a 256.000, solo para esta evaluación. Vacío usa el del revisor
  (16.000). Para modelos que razonan mucho: DeepSeek V4.1 Flash agotó los
  16.000 en 12 de 13 casos (ejecución #6) y los 32.000 en 2 de 3 (#8).
  Subirlo encarece la salida en proporción (peor caso con DeepSeek y
  256.000: ~0,31 $ por respuesta). La espera por petición crece con el tope
  (1 s por cada 100 tokens, mínimo 180 s), porque la API responde de una vez
  al terminar. Si el modelo no admite tanto, la API responde 400 sin cobrar.

El resultado sale abreviado en el resumen de la ejecución. El artefacto
`mistral-eval` guarda cada hallazgo entero (fragmento, problema, escenario y
arreglo): es lo que hay que leer para etiquetar. Si una respuesta se rechaza por el
formato (cita que no es una línea del diff, JSON incompleto…), el campo
`rechazadas` de esa revisión guarda el motivo y sus primeros 20.000
caracteres: así se sabe si el modelo vio el defecto aunque fallara el formato
(GLM 5.3 Flash en el control, ejecución #7). Ese texto solo va al artefacto,
nunca al resumen. Usa el secreto `MISTRAL_API_KEY` y la variable
`MISTRAL_MODEL` del repositorio, como el revisor.

**Coste.** Cada revisión es una solicitud (dos si la respuesta llega mal
formada). Con `mistral-large-latest` y razonamiento, del orden de 10.000
tokens de salida más la entrada (guía, contexto y diff: decenas de miles de
tokens). Doce casos a dos repeticiones son al menos 24 peticiones. Hay un
tope de 80 **peticiones HTTP reales** por ejecución, contadas en el
transporte: incluye los reintentos por errores transitorios. Si se alcanza,
la evaluación se detiene, publica lo que lleva marcado como incompleto y
termina en error. El informe da los tokens de entrada y de salida que
declara la API, para calcular el gasto con la tarifa del modelo. Un modelo
que no admite el esfuerzo de razonamiento gasta una petición de más solo la
primera vez: tras el rechazo, el resto de la ejecución ya no lo pide. Para
probar barato: `solo` con un caso y una repetición.

El JSON se guarda tras cada revisión y el paso «Evaluar» tiene su propio
límite (80 minutos, por debajo de los 90 del job). Si la ejecución se cancela
o se agota el tiempo, el artefacto `mistral-eval` conserva lo ya revisado:
`en_curso: true` si el proceso murió a mitad, `cancelada: true` si llegó a
cerrar tras la cancelación. La ejecución #5 (esfuerzo `high`, 12 casos) se
canceló a los 90 minutos sin dejar nada; esto lo evita.

Sin `--ejecutar`, el script solo lista los casos y sus objetivos y no llama
a la API:

```bash
python3 .github/scripts/mistral_eval.py
```

## Cómo añadir un caso

1. Positivo: localiza el commit con el defecto (`cabeza`), el que lo arregló
   (`arreglo`) y la base del PR (`base`). Negativo: el commit revisado, la
   base y los archivos de los hallazgos falsos.
2. Añádelo a `.github/eval/casos.json` con los SHA completos y una frase en
   `defecto` que diga qué debería verse.
3. Ejecuta el listado y comprueba que el objetivo es la función del defecto.

Si se usa la evaluación para ajustar el prompt, hay que separar casos de
ajuste y de evaluación: medir con los mismos casos con los que se ajustó solo
mide el ajuste.

## Resultados (2026-11-15)

Una repetición por caso: dan tendencia, no porcentajes. Cada hallazgo se
etiquetó a mano leyendo su problema y su escenario; «señala la función» no
basta. Costes calculados con los tokens que declara la API y la tarifa de la
página oficial de precios de Mistral (USD por millón, entrada / salida):
Large 4 0,70 / 2,10; GLM 5.3 1,40 / 4,40; GLM 5.3 Flash 0,15 / 0,50;
DeepSeek V4.1 Flash 0,30 / 1,20. Las ejecuciones #2 a #4 son anteriores al
caso de control (12 casos). Faltan a propósito: #1 (no forma parte de esta
comparación), #5 (Large 4 con esfuerzo `high`, cancelada a los 90 minutos sin
datos) y #7 y #10 (GLM 5.3 Flash antes del PR #210: el control salía inválido
por citar dos líneas; las sustituye #11).

| Ejecución | Modelo | Control | Defectos reales | Ruido en negativos | Coste |
|---|---|---|---|---|---|
| #2 | `mistral-large-latest` (Large 4) | — | 0 de 7 | 1 hallazgo inflado | ~0,75 $ (estimado) |
| #3 | `mistral-large-2512` (Large 3) | — | 0 de 7 | 7 hallazgos especulativos | ~0,22 $ (estimado) |
| #4 | `codestral-latest` | — | 0 de 7 | 3 hallazgos inútiles | ~0,12 $ (estimado) |
| #6, #8, #9 | `deepseek-v4-1-flash-1017` | acierto | 1 de 2 medidos (p125, exacto) | sin datos | 0,35 + 0,13 + 0,32 $ |
| #11 | `zai-glm-5-3-flash` | acierto | 0 de 7 | ninguno | 0,08 $ |
| #12 | `mistral-large-latest` (Large 4) | acierto | — (solo el control) | — | 0,02 $ |
| #13 | `zai-glm-5-3` | acierto | 0 de 7 (p126 cortada) | ninguno | 0,74 $ |

Lo que se aprendió:

- **Todos los modelos fiables ven el defecto evidente y ninguno ve los
  reales.** El control descarta que «0 de 7» signifique que no leen el diff:
  los defectos del historial piden algo que este revisor no tiene (contexto
  de otros archivos, conocer el proyecto). La detección sigue siendo de Codex.
- **DeepSeek V4.1 Flash es el único que acertó un defecto real** (p125, con
  el escenario de `compactar --dias 30` y un segundo hallazgo real), pero no
  termina: agotó la salida razonando en 12 de 13 casos con 16.000 tokens, en
  2 de 3 con 32.000 y en 2 de 2 con 128.000 (siempre hasta el último token).
  El esfuerzo `low` no lo frena. Descartado como revisor.
- **GLM 5.3 Flash** perdía el control por citar dos líneas seguidas (el
  validador solo admitía una); desde el PR #210 se aceptan tramos
  consecutivos de un mismo hunk y sale 13 de 13 válidas, sin ruido, en unos
  30 s por revisión. **GLM 5.3** completo da lo mismo a nueve veces el coste.
- Las tres revisiones de esta jornada que se cortaron por la espera de 180 s
  (PR #206 una vez, PR #210 dos) fueron revisiones de PR con Large 4; ninguna
  revisión de la evaluación la agotó (con topes de salida grandes la espera
  crece sola desde el PR #209). Causa probable, sin verificar: Large 4 tarda
  a veces más de 180 s según el diff.

**Decisión del mantenedor (2026-11-15):** el revisor de los PR pasa a
`zai-glm-5-3-flash` (variable `MISTRAL_MODEL`): el mismo valor que Large 4
como segunda opinión barata, a ~0,006 $ por revisión frente a ~0,04 $, más
rápido y sin ruido medido. Es un identificador fijo, sin `-latest`; los
modelos de terceros rotan rápido en Mistral (GLM 5.2 se retiró un mes después
de quedar obsoleto), así que hay que vigilar su fecha de retirada en la
página de modelos. Gasto total de la evaluación de esta jornada: ~1,73 $.
