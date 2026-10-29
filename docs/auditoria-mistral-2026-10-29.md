# Auditoría de las revisiones de Mistral

Fecha: 29 de octubre de 2026. Estado: investigación contrastada con código
histórico; las mejoras de calidad propuestas al final aún no están implementadas.

## Alcance y límites

El workflow se incorporó el **24 de octubre**, commit `57c0959`, a las 09:44
de Madrid. Se revisaron las descripciones y las conversaciones de los **42 PR
#105–146**, hasta el informe de Mistral sobre `f6d6973` en #146. Se compararon
hallazgos con snapshots de Git y se reprodujeron casos en local, sin llamar a
Mistral ni gastar crédito de API. Las respuestas de Claude y Codex son pistas,
no etiquetas de verdad: también se contrastaron con el código.

Inventario de los **últimos comentarios conservados** con la marca del bot:

| Resultado | PR | Cantidad |
|---|---|---:|
| Sin hallazgos | #109–111, #113, #115, #117–122, #124–130, #132–139, #141–146 | 32 |
| Con hallazgos | #108, #112, #114, #116, #123, #140 | 6 informes, 11 hallazgos |
| Revisión inválida | #131 | 1 |
| Sin comentario con la marca actual | #105–107 | 3 |

En los snapshots auditados, incluido `f6d6973`, el bot editaba el comentario en
cada ejecución. Por eso este inventario **no es
un recuento de ejecuciones ni permite calcular precisión o sensibilidad
históricas**. «Sin hallazgos» después de corregir un PR no prueba que Mistral
ignorara el defecto antes. Algunas rondas anteriores solo se conservan en
respuestas de Claude. Se distinguen de las salidas originales disponibles.

Hay constancia en las conversaciones de respuestas inválidas en al menos siete
PR: #116, #125–127, #131, #135 y #141. El log de la ejecución
[40594853385](https://github.com/novanoticia/email-triage-plugin/actions/runs/40594853385)
confirma el fallo sobre `b259bc2`, con 40.876 caracteres de diff. El script no
conservaba la respuesta original rechazada ni distinguía el motivo exacto:
no puede concluirse por ese mensaje si falló JSON, esquema o cita. Tampoco
atribuimos el fallo al tamaño del diff.

## Los 11 hallazgos finales

Ninguno de estos once sostiene un defecto nuevo reproducible en el snapshot
al que se refiere. Algunos contradicen mecánicamente el código; otros presentan
una decisión deliberada o una conjetura externa como si fueran un defecto.
Esto describe esta muestra final, no todas las rondas de Mistral.

| PR y snapshot | Qué afirmó Mistral | Contraste independiente |
|---|---|---|
| [#108](https://github.com/novanoticia/email-triage-plugin/pull/108#issuecomment-6381957208), `9bc0492` | La falta de `hallazgos` debe producir una lista vacía, no `None`. | Devolver `None` es el contrato de respuesta inválida; su test ya lo exige. La propuesta convertiría un fallo del formato en un resultado vacío. |
| [#112](https://github.com/novanoticia/email-triage-plugin/pull/112#issuecomment-6395257336), `78a0907`, hallazgo 1 | Rechazar contadores de caché no nulos es un error. | La tarifa guardada es para entrada sin caché. El contrato marca el coste desconocido si la API informa caché. `test_cache_informada_deja_coste_desconocido` fija justamente esa defensa. |
| #112, hallazgo 2 | Si hubiera caché, se publicaría una estimación incorrecta. | El escenario termina con coste desconocido por la defensa anterior. Afirmar comportamiento externo no suministrado tampoco prueba un fallo. |
| #112, hallazgo 3 | Sin llamadas, el coste debe ser desconocido en lugar de cero. | Si falta la credencial y no sale ninguna llamada, el coste de las llamadas realizadas es cero. El caso de llamada intentada con consumo desconocido tiene otra ruta. |
| #112, hallazgo 4 | La documentación no aclara que ZDR no se activa solo ni se verifica. | La propia cita dice «No se da por activado» y «el plugin no puede comprobarlo ni pedirlo». El texto completo en el snapshot desarrolla esa limitación. |
| [#114](https://github.com/novanoticia/email-triage-plugin/pull/114#issuecomment-6396892411), `2be71a5`, hallazgo 1 | El índice acepta evidencia fuera del recorte enviado. | `main` ya llama a `interpretar(texto, diff[:MAX_DIFF])`. Un argumento recortado sigue recortado al entrar en `indice_diff`. |
| #114, hallazgo 2 | En errores se omite el commit del comentario. | `renderizar` inserta el SHA antes de las ramas de error. El test del fallo de API comprueba esa presencia. |
| [#116](https://github.com/novanoticia/email-triage-plugin/pull/116#issuecomment-6404943978), `487e683` | Un `no_aplica` core llegaría indebidamente al proveedor. | `_principal` devuelve `None`; el correo queda `principal_no_comparable` y el bloqueo impide llamar al transporte. El cuerpo puede construirse antes: la respuesta de Claude es imprecisa en ese detalle, pero acierta sobre la ausencia de envío. |
| [#123](https://github.com/novanoticia/email-triage-plugin/pull/123#issuecomment-6412491126), `88d8131`, hallazgo 1 | Se aceptaría la suma 0,95 con tres opciones; propone tope fijo 0,01. | La entrada `[0.8, 0.1, 0.05]` se rechaza con causa `suma`, desviación 0,05. El tope sugerido rechazaría un caso válido: `[0.93, 0.03, 0.03, 0.03]`, admitido por el límite de redondeo por opción. |
| #123, hallazgo 2 | Dividir por una suma menor que 1 reduciría la confianza. | La división la aumenta: `0.7 / 0.9 > 0.7`. Además, su ejemplo `[0.7, 0.1, 0.1]` ya se rechaza por suma. El cambio contradiría la invariante de no aumentar confianza. |
| [#140](https://github.com/novanoticia/email-triage-plugin/pull/140#issuecomment-6454561305), `1d7f85b` | `umbrales` devuelve `[]` con `tiers: {}` o claves ausentes. | La ejecución de la función histórica devuelve `[4, 0]` en ambos casos, por los valores predeterminados. La entrada concreta del hallazgo no produce el resultado alegado. |

## Matices: avisos útiles y decisiones de diseño

- **#112 tuvo una objeción anterior útil sobre coste y caché.** Codex la
  corroboró y Claude [retiró expresamente su refutación](https://github.com/novanoticia/email-triage-plugin/pull/112#discussion_r4370188419).
  El arreglo es `78a0907`. No debe usarse «Claude lo rechazó» como etiqueta
  automática de alucinación. La salida original de esa ronda no es el comentario
  final de cuatro hallazgos.
- **#140 ayudó a localizar un error cercano**, aunque el escenario alegado
  por Mistral no se reproducía: el desfase de uno al cruzar el umbral se arregló
  en `a555f3c`. [Respuesta y explicación](https://github.com/novanoticia/email-triage-plugin/pull/140#issuecomment-6454588387).
  En otra ronda propuso descartar el umbral cero: `margen_umbral(1, 0) == 2`
  demuestra que sí es relevante para pasar a ARCHIVE.
- **#127 partió de un supuesto externo no demostrado**, sobre `tool_use` en
  entradas `user` del host. Se aceptó ampliar defensivamente el lector. Es una
  [mejora defensiva aceptada](https://github.com/novanoticia/email-triage-plugin/pull/127#issuecomment-6418965750),
  no prueba de que el host hubiera producido el caso citado.
- **#141 mezcla diseño y hechos falsos.** La decisión inicial sobre tolerancia
  en híbrido correspondía al mantenedor; afirmar que faltaba revisión obligatoria
  sí contradice el literal `revision_obligatoria=True` en `9c72677`.
  [Respuesta conservada](https://github.com/novanoticia/email-triage-plugin/pull/141#issuecomment-6455006133).

## Qué demuestra la revisión del propio PR #146

La nueva sección de comprobaciones da más visibilidad, pero **también puede
contener alucinaciones**. Mistral afirmó que el contexto se recorta «sin truncar
líneas ni romper sintaxis» y lo marcó como revisado:
[informe sobre `f6d6973`](https://github.com/novanoticia/email-triage-plugin/pull/146#issuecomment-6490777443).
El código hace `fragmento = texto[:limite]`. Con el texto
`def funcion():\n    return "cadena larga"\n` y límite 29, se obtiene
`def funcion():\n    return "ca`, que produce `SyntaxError` al compilarlo.
El recorte está documentado y no se ejecuta: esto refuta la afirmación del
revisor, no demuestra por sí solo un fallo funcional del recorte.

Codex encontró además una **regresión real** de nuestra implementación:
[los cambios sin hunks nunca admitían comprobaciones válidas](https://github.com/novanoticia/email-triage-plugin/pull/146#discussion_r4409750361).
Un renombrado puro, un cambio de permisos o un binario producen diff no vacío,
pero `indice_diff` solo contiene archivos con líneas de hunks. La corrección
usa un inventario separado de rutas para las comprobaciones y conserva el
índice estricto de líneas para las citas de hallazgos.

El contexto añadido también necesita mejorar su selección. En `f6d6973`, enviar
los primeros 10.000 caracteres de `triage_helpers.py` llega solo a la línea 150,
todavía en el docstring; el archivo tiene más de 6.000 líneas. Los comienzos de
`modelos.py` y `clasificadores.py` tampoco aportan muchas funciones relevantes.
La guía se corta a 20.000 caracteres, antes de parte de sus convenciones.
Más caracteres no garantizan que el modelo vea las guardas que necesita.

## Mejoras propuestas, en orden

1. **Guardar evidencia de cada ejecución.** Mantener el comentario resumido,
   pero conservar un artefacto por SHA e intento: base/cabeza, modelo pedido y
   resuelto, hash del prompt, inventario del contexto, respuesta del modelo y
   motivo específico de rechazo (`json_invalido`, `campo_ausente`,
   `ruta_no_enviada`, `cita_no_encontrada`). No incluir claves ni cuerpos de
   errores HTTP. Impide perder la historia al repetir hasta obtener verde.
2. **Construir una evaluación con casos reales antes de ajustar el prompt.**
   Fijar commit, entrada y resultado para cada caso; separar casos de ajuste
   y evaluación. Usar los falsos hallazgos anteriores como negativos y defectos
   reales anteriores a su arreglo como positivos. Repetir un número fijo de
   veces y medir falsos positivos, defectos recuperados, invalidez y variación.
   Los tests de JSON y transporte no miden calidad de razonamiento.
3. **Seleccionar contexto por funciones y flujo.** En Python, extraer la
   función completa que contiene el cambio, sus guardas, productores y
   consumidores pertinentes, y tests relacionados; distinguir código base y
   cabeza. En otros formatos, usar ventanas alrededor del cambio. Mostrar
   archivo, líneas y omisiones y priorizar por relevancia, no por alfabeto.
4. **Exigir un intento de refutación para cada candidato.** Antes de publicarlo,
   contrastar valores predeterminados, guardas previas, camino alcanzable,
   contrato y tests; identificar por qué lo introduce el PR. Diferenciar la
   línea nueva de una eliminada. Comprobar también qué casos válidos rompe el
   arreglo sugerido. Si falta evidencia externa o contexto, dejarlo pendiente.
   Una cita literal valida ubicación, no causalidad.
5. **Evaluar una segunda pasada solo si mejora las métricas.** Podría intentar
   refutar candidatos con contexto dirigido, pero el mismo modelo puede repetir
   el mismo error. No presentarla como verificación independiente ni como cura
   demostrada. Registrar su coste y comparar con el mismo conjunto de casos.

No conviene forzar una cuota de defectos, aumentar el texto sin selección,
repetir hasta verde ni considerar una afirmación cierta solo porque pasa un
esquema o lleva severidad alta.

## Casos positivos para la evaluación

Estos son puntos de partida con un cambio de comportamiento comprobable; no
etiquetan automáticamente la revisión final de Mistral como falso negativo.

| Caso | Antes / después | Resultado que debe detectar la evaluación |
|---|---|---|
| #123, límite flotante | anterior a `7bc8efb` / `88d8131` | `[0.93,0.03,0.03,0.03]` supera 0,02 por representación binaria; el margen `1e-9` permite el límite válido. |
| [#125, retención](https://github.com/novanoticia/email-triage-plugin/pull/125#discussion_r4376477046) | `525b989` / `09633bb` | Con sello real reciente y `ts` del modelo en 1999, no debe purgarse el registro reciente. Reproducción: antes conserva 0/1; después 1/1. |
| [#126, extracto con añadido](https://github.com/novanoticia/email-triage-plugin/pull/126#discussion_r4378274530) | `9091acc` / `bf6f8e0` | Buscar una subcadena acepta un cuerpo alterado; comparar la entrega completa lo rechaza. |
| [#143, id numérico](https://github.com/novanoticia/email-triage-plugin/pull/143#discussion_r4408562012) | anterior a `fa3ce89` / `fa3ce89` | Omitir la copia de respuesta y leerla del transcript debe normalizar el id igual que la ruta con copia. |
| #146, sin hunks | `f6d6973` / corrección de este PR | Un renombrado puro, permisos o binario debe permitir comprobar su ruta sin inventar líneas de evidencia. |

## Verificaciones realizadas

- `78a0907`: 31 tests de Decisions, sin fallos.
- `88d8131`: 48 tests de Decisions y diagnóstico, sin fallos; invocación
  directa de los dos escenarios inválidos y el límite válido de #123.
- `2be71a5`: 37 tests del revisor y de sus citas, sin fallos.
- Ejecución de funciones históricas de #140 y #125 extraídas por AST;
  inspección del flujo y de los contratos en los snapshots citados.
- Reproducción del recorte a mitad de cadena del informe de #146.
- Lectura de las conversaciones de los 42 PR y de los logs de muestra de
  #141 y #146 mediante el conector de GitHub.

No se han realizado llamadas de evaluación a Mistral en esta investigación.
La mejora de calidad que pueda aportar cada propuesta está pendiente de medir.

Actualización posterior a la auditoría: a petición del mantenedor, el revisor
publica un comentario nuevo por resultado, con SHA y enlace a la ejecución y
al intento de Actions. Esto conserva el historial futuro; no recupera las
versiones anteriores que se sobrescribieron. Los artefactos estructurados y
los diagnósticos detallados propuestos arriba siguen pendientes.
