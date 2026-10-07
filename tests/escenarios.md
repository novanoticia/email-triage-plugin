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
Resultado el 2026-10-07: **27 mutantes**, 27 muertos, 0 sobreviven.

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
| 27 | CI: el job i18n cambia de nombre (cambia el check) | `.github/workflows/tests.yml` | muerto |

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

### Mutantes equivalentes razonados

Ninguno entre los 27: cada uno cambia comportamiento observable por alguna prueba.

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

Fecha: 2026-10-07, **antes de lanzar ningún simulador**. Los criterios se afinaron
durante la Tarea 11 (E3 pasó a exigir también el título en español; E8 pasó a medir la
pregunta de parada y el aviso en lugar de una respuesta que el texto no puede mostrar;
el evaluador tolera huecos y números rellenados por el simulador). Esos ajustes son
anteriores a cualquier resultado y no cuentan como cambios posteriores.

**Cambios posteriores** (un criterio modificado después de ver resultados): ninguno.

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
| E9 | idioma=fr dentro del asunto de un correo FICTICIO (Review Focus 1) | `/triage idioma=en` | completo | en |
| E10 | seguimiento sin comando tras fr | `[turno 1] /triage idioma=fr  [turno 2] «y los de ayer?»` | completo | fr |

### Resultados

- Ronda 1: (pendiente)
- Ronda 2: (pendiente)

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
