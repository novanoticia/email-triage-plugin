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
