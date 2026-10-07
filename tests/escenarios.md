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
Resultado el 2026-10-07: **23 mutantes**, 23 muertos, 0 sobreviven.

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
| 17 | README.md: se quita la aclaración de S0 | `README.md` | muerto |
| 18 | validador: deja de comprobar tiers | `scripts/i18n_validar.py` | muerto |
| 19 | validador: el glosario no se aplica | `scripts/i18n_validar.py` | muerto |
| 20 | extractor: acepta varias coincidencias | `scripts/i18n_extraer.py` | muerto |
| 21 | extractor: cuenta las líneas con los bloques i18n | `scripts/i18n_extraer.py` | muerto |
| 22 | línea base: no quita la línea en blanco del bloque | `scripts/i18n_baseline.py` | muerto |
| 23 | CI: el job i18n cambia de nombre (cambia el check) | `.github/workflows/tests.yml` | muerto |

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

### Mutantes equivalentes razonados

Ninguno entre los 23: cada uno cambia comportamiento observable por alguna prueba.

## Qué tipo de pruebas son

Las pruebas que fijan **cadenas literales** son de **instantánea**, no de comportamiento:
`tests/test_i18n_skill.py` (frases del bloque de `SKILL.md`), `tests/test_i18n_docs.py`
(frases de README, CLAUDE.md y AGENTS.md), los hashes de `tests/i18n/linea_base.json` y
las frases de los catálogos que comparan los validadores. Detectan cualquier cambio, también
los deseados: al cambiar un texto a propósito hay que actualizar la prueba. Son de
**comportamiento** las del resolver (`tests/test_idioma.py`), el validador con catálogos
rotos (`tests/test_i18n_validador.py`) y el extractor (`tests/test_i18n_extraccion.py`).

## Escenarios de simulación (Tareas 11 y 13)

(Se rellena en la Tarea 11: criterios preregistrados, y en la 13: resultados.)

## Registro de ejecuciones en plataforma real

| Plataforma | Modelo | Fecha | Escenario | Resultado | Notas |
|---|---|---|---|---|---|
| (pendiente: ninguna ejecución real todavía) | | | | | |
