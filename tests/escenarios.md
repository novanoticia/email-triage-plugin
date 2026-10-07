# Registro de verificación i18n (escenarios y mutantes)

> Elaborado con asistencia de IA; requiere revisión humana.

Este fichero registra **cómo se ha verificado** el soporte multiidioma y **con qué
límites**. Distingue tres niveles y nunca los mezcla:

1. **Pruebas automáticas** (`python3 -m unittest discover -s tests -t .`).
2. **Simulado con subagentes** (sección «Escenarios», se rellena en la Tarea 11 y 13).
3. **Ejecutado en la plataforma real** (Claude Code / Cowork): **no ejecutado**. Esto
   no es una plataforma real; mientras esa tabla esté vacía, nada de lo anterior es
   «verificado» en el sentido de que un modelo real siga el bloque de `SKILL.md`.

## Mutantes (sabotaje de las pruebas) — Tarea 10

Herramienta: `python3 scripts/i18n_mutar.py` (aplica cada mutación sobre una copia del
repositorio y ejecuta toda la suite; un mutante que sobrevive es un hueco).
Resultado el 2026-10-07: **59 mutantes**, 59 muertos, 0 sobreviven.

| # | Mutante | Fichero | Resultado |
|---|---------|---------|-----------|
| 1 | resolver: primera marca -> última | `plugins/email-triage/skills/email-triage/scripts/idioma.py` | muerto |
| 2 | resolver: acepta una palabra pegada como marca | `plugins/email-triage/skills/email-triage/scripts/idioma.py` | muerto |
| 3 | resolver: un código sin catálogo no cae a es | `plugins/email-triage/skills/email-triage/scripts/idioma.py` | muerto |
| 4 | resolver: glosario.yaml cuenta como idioma | `plugins/email-triage/skills/email-triage/scripts/idioma.py` | muerto |
| 5 | resolver: una config vacía avisa | `plugins/email-triage/skills/email-triage/scripts/idioma.py` | muerto |
| 6 | resolver: códigos de 3 letras no valen | `plugins/email-triage/skills/email-triage/scripts/idioma.py` | muerto |
| 7 | en.yaml: un tier traducido | `plugins/email-triage/skills/email-triage/i18n/en.yaml` | muerto |
| 8 | fr.yaml: una clave vaciada | `plugins/email-triage/skills/email-triage/i18n/fr.yaml` | muerto |
| 9 | fr.yaml: figura como revisado sin revisor | `plugins/email-triage/skills/email-triage/i18n/fr.yaml` | muerto |
| 10 | en.yaml: una frase de confirmación pierde el riesgo alto | `plugins/email-triage/skills/email-triage/i18n/en.yaml` | muerto |
| 11 | SKILL.md: se quita S0–S5 de las precedencias | `plugins/email-triage/skills/email-triage/SKILL.md` | muerto |
| 12 | SKILL.md: el límite de S0 cambia | `plugins/email-triage/skills/email-triage/SKILL.md` | muerto |
| 13 | SKILL.md: la regla «prevalece sobre todas» | `plugins/email-triage/skills/email-triage/SKILL.md` | muerto |
| 14 | SKILL.md: el aviso de idioma desconocido va al final | `plugins/email-triage/skills/email-triage/SKILL.md` | muerto |
| 15 | SKILL.md: la marca se leería también en los correos | `plugins/email-triage/skills/email-triage/SKILL.md` | muerto |
| 16 | SKILL.md: se altera una línea original | `plugins/email-triage/skills/email-triage/SKILL.md` | muerto |
| 17 | README.md: se quita la aclaración de S0 de la sección Language / Langue | `README.md` | muerto |
| 18 | validador: deja de comprobar tiers | `scripts/i18n_validar.py` | muerto |
| 19 | validador: el glosario no se aplica | `scripts/i18n_validar.py` | muerto |
| 20 | extractor: acepta varias coincidencias | `scripts/i18n_extraer.py` | muerto |
| 21 | extractor: cuenta las líneas con los bloques i18n | `scripts/i18n_extraer.py` | muerto |
| 22 | línea base: no quita la línea en blanco del bloque | `scripts/i18n_baseline.py` | muerto |
| 23 | evaluador: no comprueba el orden | `tests/i18n/evaluador.py` | muerto |
| 24 | evaluador: debe_contener siempre pasa | `tests/i18n/evaluador.py` | muerto |
| 25 | evaluador: los huecos entre corchetes no se rellenan | `tests/i18n/evaluador.py` | muerto |
| 26 | escenario E1: el ejemplo que debe fallar pasa | `tests/escenarios_i18n.yaml` | muerto |
| 27 | bloque: la regla central se invierte (si idioma = es) | `plugins/email-triage/skills/email-triage/SKILL.md` | muerto |
| 28 | bloque: la config gana a la marca | `plugins/email-triage/skills/email-triage/SKILL.md` | muerto |
| 29 | bloque: el fallo seguro opera en en | `plugins/email-triage/skills/email-triage/SKILL.md` | muerto |
| 30 | bloque: el aviso de IA pasa a ser la última línea | `plugins/email-triage/skills/email-triage/SKILL.md` | muerto |
| 31 | bloque: el aviso de IA va después de los banners | `plugins/email-triage/skills/email-triage/SKILL.md` | muerto |
| 32 | bloque: se borra la regla de clave ausente (Review Focus 4) | `plugins/email-triage/skills/email-triage/SKILL.md` | muerto |
| 33 | bloque: las equivalencias pasan a solo sí/no (Review Focus 5) | `plugins/email-triage/skills/email-triage/SKILL.md` | muerto |
| 34 | bloque: un código suelto también es marca | `plugins/email-triage/skills/email-triage/SKILL.md` | muerto |
| 35 | bloque: lo que se escribe en disco sí se traduce | `plugins/email-triage/skills/email-triage/SKILL.md` | muerto |
| 36 | bloque: el seguimiento sin comando vuelve a es (persistencia) | `plugins/email-triage/skills/email-triage/SKILL.md` | muerto |
| 37 | bloque: se deja de avisar de entrada_invalida | `plugins/email-triage/skills/email-triage/SKILL.md` | muerto |
| 38 | triage.md: se quita «un código suelto no cambia nada» | `plugins/email-triage/commands/triage.md` | muerto |
| 39 | en.yaml: respuesta afirmativa en español | `plugins/email-triage/skills/email-triage/i18n/en.yaml` | muerto |
| 40 | en.yaml: la confirmación de deshacer mezcla (sí/no) | `plugins/email-triage/skills/email-triage/i18n/en.yaml` | muerto |
| 41 | fr.yaml: el aviso de IA sale en inglés | `plugins/email-triage/skills/email-triage/i18n/fr.yaml` | muerto |
| 42 | en.yaml: lote.confirmar copiado de es y marcado invariable | `plugins/email-triage/skills/email-triage/i18n/en.yaml` | muerto |
| 43 | fr.yaml: entrada.negativo pierde «annuler» | `plugins/email-triage/skills/email-triage/i18n/fr.yaml` | muerto |
| 44 | en.yaml: correo.recomendacion con opciones en español | `plugins/email-triage/skills/email-triage/i18n/en.yaml` | muerto |
| 45 | fr.yaml: lote.confirmar con «Puedes» | `plugins/email-triage/skills/email-triage/i18n/fr.yaml` | muerto |
| 46 | en.yaml: el marcador de inyección se traduce | `plugins/email-triage/skills/email-triage/i18n/en.yaml` | muerto |
| 47 | resolver: un JSON inválido degrada sin avisar | `plugins/email-triage/skills/email-triage/scripts/idioma.py` | muerto |
| 48 | resolver: el modo --texto ignora el mensaje | `plugins/email-triage/skills/email-triage/scripts/idioma.py` | muerto |
| 49 | validador: deja de exigir marcadores de máquina idénticos | `scripts/i18n_validar.py` | muerto |
| 50 | validador: deja de comparar palabras del original en riesgo alto | `scripts/i18n_validar.py` | muerto |
| 51 | validador: deja de vigilar letras no ASCII en inglés | `scripts/i18n_validar.py` | muerto |
| 52 | validador: `invariable` vuelve a bastar con declararlo | `scripts/i18n_validar.py` | muerto |
| 53 | extractor: no vuelca la marca maquina | `scripts/i18n_extraer.py` | muerto |
| 54 | línea base: deja de vigilar references/* | `scripts/i18n_baseline.py` | muerto |
| 55 | evaluador: el umbral de letras fijas se anula | `tests/i18n/evaluador.py` | muerto |
| 56 | evaluador: se ignora el turno 2 | `tests/i18n/evaluador.py` | muerto |
| 57 | escenario E10: se quita el criterio del turno 2 | `tests/escenarios_i18n.yaml` | muerto |
| 58 | CI: el job i18n vuelve a un clon superficial | `.github/workflows/tests.yml` | muerto |
| 59 | CI: el job i18n cambia de nombre (cambia el check) | `.github/workflows/tests.yml` | muerto |

**Corrección importante (Tarea 12): la auto-muerte de los mutantes.** Las dos primeras
ejecuciones de la herramienta (23 de 23 en la Tarea 10 y 27 de 27 en la Tarea 11) **no
demostraban nada**: la suite se ejecuta dentro de la copia mutada, y
`tests/test_i18n_mutar.py` comprueba que el texto a mutar existe, así que **fallaba en
toda copia mutada** y todo mutante «moría» por ese test y no por una prueba del
comportamiento. Se detectó porque un mutante del README «moría» sin que ninguna prueba de
documentación lo notara. Arreglo: la herramienta marca `I18N_MUTANDO=1` y ese test se
omite dentro de la copia (con un test que prueba que se omite allí y falla fuera).
Primera ejecución honesta: **26 de 27** muertos; sobrevivía la aclaración de S0 de la
sección Language / Langue (el README la repite en el changelog y el test aceptaba
cualquiera de las dos). Se cerró exigiéndola dentro de esa sección. Resultado final: ver
arriba.

La herramienta se probó a sí misma: un mutante equivalente (cambiar solo el docstring de
`idioma.py`) sí se reporta como superviviente, y un mutante cuyo texto no existe se
reporta como «no aplicable» (cuenta como superviviente).

### Huecos encontrados durante el trabajo y cerrados

| Tarea | Hueco | Cierre |
|-------|-------|--------|
| 2 | Nada comprobaba los códigos de 3 letras (`[a-z]{2,3}` -> `{2}` sobrevivía) | `test_codigo_de_tres_letras_valido_y_de_cuatro_no` |
| 4 | Sobrevivían «estructura inválida» y «glosario ilegible» al anular cada comprobación del validador | `test_estructura_sin_frases`, `test_glosario_ilegible` |
| 4 | Falso positivo: el verbo inglés «ARCHIVE» coincide con el tier | el validador compara tiers solo en frases cuyo original los nombra |
| 8 | `TestEstadoVigilado` leía el README sin normalizar espacios: la frase vigilada está partida en dos líneas y la prueba pasaba en vacío | el test normaliza espacios; el mutante «fr revisado» ahora muere |
| 12 | Auto-muerte: el test de aplicabilidad hacía «morir» a todo mutante (ver arriba) | `I18N_MUTANDO` + `TestLaCopiaMutadaNoSeAutoMata` |
| 12 | Sobrevivía la aclaración de S0 de la sección Language / Langue (el changelog repite la frase) | `test_la_aclaracion_esta_en_la_seccion_language_langue…` |

| 13 | Revisión independiente: 22 de sus 25 mutantes sobrevivían (el bloque de `SKILL.md` solo tenía pruebas de subcadenas sueltas; `invariable` autodeclarado; idioma mezclado en frases de riesgo alto) | pruebas semánticas del bloque, validador endurecido y 32 mutantes nuevos en la herramienta |
| 13 | **Segunda auto-muerte**: con el registro de mutantes desactualizado, la suite fallaba en TODA copia y los «59 de 59» no valían | la herramienta se niega a medir si la suite sin mutar no pasa (`SuiteSinMutarRoja`) |

### Mutantes equivalentes razonados

Ninguno entre los 59: cada uno cambia comportamiento observable por alguna prueba.

## Qué tipo de pruebas son

Las pruebas que fijan **cadenas literales** son de **instantánea**, no de comportamiento:
`tests/test_i18n_skill.py` (frases del bloque de `SKILL.md`), `tests/test_i18n_docs.py`
(frases de README, CLAUDE.md y AGENTS.md), los hashes de `tests/i18n/linea_base.json` y
las frases de los catálogos que comparan los validadores. Detectan cualquier cambio, también
los deseados: al cambiar un texto a propósito hay que actualizar la prueba. Son de
**comportamiento** las del resolver (`tests/test_idioma.py`), el validador con catálogos
rotos (`tests/test_i18n_validador.py`) y el extractor (`tests/test_i18n_extraccion.py`).

## Escenarios de simulación (Tareas 11 y 13)

### Método

- Cada escenario lo recibe un subagente **de contexto limpio** con **solo** el paquete
  (la carpeta de la skill, copiada tal cual; no hay script de empaquetado) y el mensaje
  del escenario **pegado en el prompt**. El simulador declara qué ficheros leyó y qué le
  pareció ambiguo (citando la frase).
- Los criterios están en `tests/escenarios_i18n.yaml` y los aplica
  `tests/i18n/evaluador.py`. Los textos esperados salen de los catálogos, nunca escritos a
  mano. Cada criterio lleva un ejemplo que debe pasar y otro que debe fallar, y una prueba
  lo exige (`tests/test_i18n_escenarios.py`).
- Se **leen las respuestas y las notas**, no solo el veredicto del evaluador: pueden
  aparecer hallazgos que ningún criterio preveía.
- Casos **ficticios**: ningún correo ni dirección reales.
- Tras corregir, se repiten **solo los escenarios afectados** (ronda 2) con simuladores
  nuevos y el paquete reconstruido; los criterios no cambian entre rondas.

### Preregistro

Fecha: 2026-10-07, **antes de lanzar ningún simulador**: E1–E10 con sus criterios. Los
ajustes hechos durante la Tarea 11 (E3 exige también el título en español; E8 mide la
pregunta de parada y el aviso; el evaluador tolera huecos y números rellenados) son
anteriores a cualquier resultado y no cuentan como cambios posteriores.

**Cambios posteriores** (criterios o evaluador modificados DESPUÉS de ver resultados de la
ronda 1; el registro anterior decía «ninguno» y era falso en cuanto se tocó el evaluador:
hallazgo I-1 de la revisión independiente):

1. **Cambio posterior 1 — evaluador (falsos positivos).** `tests/i18n/evaluador.py` marcaba
   como «frase exclusiva de otro idioma» plantillas casi todo huecos (`   ▲ [..] | [..]`) y
   marcadores entre corchetes con sangría, que casaban con cualquier texto. Afectó a E1, E4,
   E5 y E9 (cuatro «FALLA» que eran respuestas correctas, leídas a mano). Se corrigió
   (`letras_fijas` ≥ 8 y marcador entero entre corchetes = literal) con 4 tests.
2. **Cambio posterior 2 — E10 mide el turno 2.** E10 pasaba con el turno 2 en español porque el
   criterio solo miraba el turno 1: ahora exige `aviso.ia` y la etiqueta del idioma en el
   turno 2 (`turno2` en el criterio y evaluador).
3. **Cambio posterior 3 — E9 sin contaminación.** El mensaje preregistrado de E9 llevaba el
   asunto «Oferta idioma=fr» DENTRO del mensaje del usuario, así que no probaba el riesgo real
   (la marca en los datos). Ahora el mensaje es `/triage idioma=en` y el asunto va como contexto.
4. **Cambio posterior 4 — E1 y E7 exigen el orden del aviso.** El aviso de IA debe ir antes del
   banner de modo (E1) y antes de la marca de hora (E7): regla explícita añadida al bloque tras
   las notas de los simuladores y el hallazgo m-7 de la revisión.
5. **Cambio posterior 5 — E11 nuevo.** Frase de activación de dry-run en francés (hallazgo I-5):
   escenario añadido tras la revisión, no preregistrado.

Los cambios 2–5 solo **endurecen** criterios (no relajan ninguno); el 1 corrige un evaluador que
fallaba respuestas correctas.

| Id | Qué comprueba | Mensaje | Paquete | Idioma esperado |
|----|---------------|---------|---------|-----------------|
| E1 | dry-run en inglés | `/triage dry-run idioma=en` | completo | en |
| E2 | sesión real en francés | `/triage idioma=fr` | completo | fr |
| E3 | idioma sin catálogo (de) | `/triage idioma=de` | completo | es |
| E4 | sin marca -> español idéntico, sin aviso | `/triage` | completo | es |
| E5 | «en» suelto no es marca | `/triage filtra en Leer Después` | completo | es |
| E6 | solo SKILL.md, sin catálogos, pide fr | `/triage idioma=fr` | solo_skill | es |
| E7 | modo rutina en inglés | `<scheduled-task> triaje idioma=en` | completo | en |
| E8 | parada de confirmación en francés, modo lote (Review Focus 5) | `/triage idioma=fr` | completo | fr |
| E9 | idioma=fr dentro del asunto de un correo FICTICIO, en los datos y no en el mensaje (Review Focus 1) | `/triage idioma=en` | completo | en |
| E10 | seguimiento sin comando tras fr | `[turno 1] /triage idioma=fr  [turno 2] «y los de ayer?»` | completo | fr |
| E11 | frase de activación de dry-run en francés (hallazgo I-5; añadido tras la revisión) | `/triage simule le triage idioma=fr` | completo | fr |

### Resultados

**Ronda 1 (2026-10-07, 10 simuladores `sonnet`, paquete = carpeta de la skill en el commit
`f8092d6`; E6 solo con `SKILL.md`).** Resultado del evaluador: tras el cambio posterior 1,
10 de 10 «PASA»; con el evaluador original, 4 «FALLA» (todos falsos positivos). **Pasar los
criterios no es lo importante**: lo que cuenta salió de leer las respuestas y las notas.

| Id | Evaluador | Qué reveló la lectura de respuesta y notas |
|----|-----------|--------------------------------------------|
| E1 | PASA | El aviso de IA iba primero, pero el paquete no ordenaba aviso vs banner de simulación (ambigüedad citada). La «lista de opciones es un literal, no una instrucción» se leyó como «elige una». Plurales «1 emails» (igual que «1 correos» en `es`). |
| E2 | PASA | Correcto en francés. Duda: ¿los nombres reales de carpeta y de criterios se traducen? (no estaba dicho). |
| E3 | PASA | Aviso de idioma desconocido al principio y sesión en `es`: correcto. Formato de la lista de disponibles improvisado. |
| E4 | PASA | `es` sin marca idéntico al original, sin leer catálogos. |
| E5 | PASA | «en» suelto tratado como texto: `es`, sin catálogos. |
| E6 | PASA | Con solo `SKILL.md`: línea multilingüe de respaldo y salida en `es`. Duda: ¿hace falta `aviso.ia` en el fallo? (no: nada sale traducido; ahora dicho). |
| E7 | PASA | Aviso antes de las horas. Ambigüedad entre el anuncio inicial y la línea de resumen de rutina (dos claves). |
| E8 | PASA | Parada en francés con aviso primero. El simulador declaró que trataría «oui» como afirmativo citando `entrada.afirmativo`. |
| E9 | PASA | La marca del asunto se trató como dato. Pero el mensaje contaminaba el escenario (cambio 3) y `idioma.py` devolvió un aviso `repetida` que el paquete no decía si mostrar. |
| E10 | PASA | **Hueco real:** el turno 2 (sin marca) salió en **español** y sin aviso de IA: el bloque no definía la persistencia entre turnos. El criterio original no lo medía (cambio 2). |

Ronda 2: se repiten solo los escenarios afectados por los arreglos (E1, E2, E6, E7, E8, E9,
E10 y E11 nuevo): **(pendiente de ejecutar en este momento)**.

### Revisión independiente (Tarea 13)

Revisor de contexto limpio, solo lectura, sobre `f8092d6`: **0 críticos, 7 importantes, 13
menores**. De sus 25 mutantes propios, **22 sobrevivían** a la suite de entonces (3 muertos,
todos por causas incidentales): las pruebas del bloque de `SKILL.md` eran de instantánea sobre
subcadenas sueltas. Los 7 importantes se corrigen en la pasada de arreglos con pruebas
previas (ver ledger en el informe final); los menores quedan como pendientes.

### Límites del método (léelos antes de fiarte de un resultado)

- **Esto es una simulación, no una plataforma real**: no se ha ejecutado en Claude Code ni
  en Cowork.
- Los simuladores no están aislados a nivel de sistema: su lista de ficheros leídos es
  **autodeclarada**.
- Un simulador por escenario **no mide la variabilidad** del modelo.
- El revisor y los simuladores son modelos: **no son revisión humana**.

## Registro de ejecuciones en plataforma real

| Plataforma | Modelo | Fecha | Escenario | Resultado | Notas |
|---|---|---|---|---|---|
| (pendiente: ninguna ejecución real todavía) | | | | | |
