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
negativos (#108, #114, #116, #123, #140).

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

**Actions → Mistral Eval → Run workflow.** Dos campos:

- `repeticiones`: revisiones por caso (2 por defecto).
- `solo`: ids separados por comas; vacío evalúa todos.

El resultado sale en el resumen de la ejecución y, completo, en el artefacto
`mistral-eval`. Usa el secreto `MISTRAL_API_KEY` y la variable
`MISTRAL_MODEL` del repositorio, como el revisor.

**Coste.** Cada revisión es una solicitud (dos si la respuesta llega mal
formada). Con `mistral-large-latest` y razonamiento, del orden de 10.000
tokens de salida más la entrada (guía, contexto y diff: decenas de miles de
tokens). Doce casos a dos repeticiones son al menos 24 solicitudes. Hay un
tope de 80 por ejecución. Para probar barato: `solo` con un caso y una
repetición.

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
