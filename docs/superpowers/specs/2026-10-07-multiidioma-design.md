# Diseño: soporte multiidioma (es · en · fr)

- **Fecha:** 2026-10-07
- **Commit base:** `2c98507` (v3.13.5, `main`)
- **Versión objetivo:** 3.14.0 (minor)
- **Estado:** borrador para revisión humana. Elaborado con asistencia de IA; requiere revisión humana.

## 1. Objetivo y criterio de éxito

Que quien use el plugin reciba lo que el skill le muestra en su idioma, y que
añadir un idioma cueste soltar un fichero.

**Criterio principal:** con el idioma por defecto (`es`) la salida es idéntica a
la del commit base. Lista de líneas del original que se modifican: **cero**; todo
son adiciones.

## 2. Decisiones del usuario (Fase 2)

| Tema | Decisión |
|---|---|
| Idiomas | `es` (defecto y referencia), `en`, `fr` |
| Alcance | Capa 2: lo que el skill muestra a la persona + que el agente responda en el idioma elegido. Del README, solo una sección corta «Language / Langue» |
| Fuera de alcance | Instrucciones internas (`SKILL.md`, `references/`), README completos en `en`/`fr`, nombres de tiers, claves, modos y marcadores S0–S5, mensajes de error de los scripts |
| Selección | Solo explícita (ver §3). Sin detección automática ni variable de entorno |
| Artefactos en disco | Nunca se traducen (JSONL, volcados) |
| Revisión | Nadie por ahora: `en` y `fr` son `borrador-ia` |
| Aviso | Breve, al principio de **toda** salida traducida; en `es` no sale |
| Contenido sensible | Ninguno clínico/legal. Las frases de confirmar mover, archivar y deshacer se marcan `riesgo: alto` |
| Publicación | Puede subirse la rama de trabajo tras cada tarea; nunca a `main`; PR y Release solo bajo petición |
| Nivel Git del usuario | 1: guías web paso a paso |

## 3. Selección del idioma

La marca es explícita, porque el texto de `/triage` es lenguaje natural y un
`en` o `es` suelto chocaría con la preposición o el verbo españoles.

| Entrada | Resultado |
|---|---|
| `idioma=en` o `lang=en` en cualquier punto | `en` |
| `idioma=EN`, `idioma=en-US`, `idioma=fr_FR.UTF-8` | se normaliza (lo anterior al primer `-`, `_` o `.`, en minúscula, 2–3 letras): `en`, `en`, `fr` |
| `idioma=es` | `es` (idéntico al original) |
| `idioma=de` (válido, sin catálogo) | aviso en `es` al principio con los disponibles; se ejecuta en `es` |
| `idioma=` vacío o `idioma=xx1` | igual que el anterior |
| `idioma=en idioma=fr` | gana el primero y se avisa |
| `en` / `es` sueltos, `filtra en Leer Después` | no hay código; texto normal |
| sin marca | `usuario.idioma` de `config.yaml`; si falta o está vacío, `es` |

Persistencia: cada invocación de `/triage` decide su idioma; solo los mensajes de
seguimiento sin comando conservan el anterior.

`config.yaml` ya contiene `usuario.idioma: "es"` (comentario «Idioma para los
resúmenes»), clave que hoy **nadie lee**. Se reutiliza. Efecto a documentar en el
CHANGELOG: quien la hubiera cambiado pasará a ver ese idioma.

## 4. Estructura

Todo dentro de `plugins/email-triage/skills/email-triage/` para viajar en el paquete.

```
i18n/es.yaml      # generado por script desde el original; referencia
i18n/en.yaml      # borrador-ia
i18n/fr.yaml      # borrador-ia
i18n/README.md    # cómo añadir un idioma (español)
scripts/idioma.py # resuelve/valida el código y lista los idiomas autodescubiertos
```

- Añadir un idioma = soltar `i18n/<código>.yaml`. Ningún fichero principal los enumera.
- `idioma.py` es un módulo nuevo: `triage_helpers.py` y su test no cambian. Si el
  script no está disponible, el modelo aplica la tabla de §3 a mano.
- `es.yaml` lo genera un script de extracción que lee los literales reales y falla
  si alguno no existe en el original.

## 5. Catálogo

```yaml
estado: borrador-ia        # referencia | borrador-ia | experimental | revisado
redactado_por: IA
revisado_por: null
frases:
  resumen.titulo_real:
    texto: "RESUMEN DE TRIAJE v3.0"
    origen: original       # original | nuevo
    fuente: "SKILL.md:938"
    riesgo: normal         # normal | alto
    invariable: false
```

- Un literal, una clave: encabezados, rótulos, etiquetas, preguntas de parada y cada
  lista de opciones (`MOVER / DEJAR / ARCHIVAR`, `sí/no`, `LEER AHORA / PUEDE ESPERAR`).
  Sin frases compuestas con trozos traducidos.
- Se distingue «literal del catálogo, cópialo tal cual» de «hueco o instrucción entre
  corchetes, redáctala tú» (`[Asunto]`, `[destino]`).
- Los tiers y los modos no llevan clave: se emiten siempre sin traducir. Pueden ir con
  un rótulo traducido al lado.
- Entrada por equivalencia: el catálogo lista las respuestas aceptadas por idioma
  (sí/yes/oui, cancelar/cancel/annuler) y las frases de activación de dry-run, veloz
  y undo.
- Las preguntas de los 30 criterios (`question:` de `config.yaml`) entran como claves
  propias; `config.yaml` no cambia.
- Glosario por idioma, vigilado por una prueba.

## 6. Bloque en `SKILL.md` y precedencias

Bloque delimitado `<!-- i18n:inicio -->` … `<!-- i18n:fin -->`, con línea en blanco
antes y después, ≤ 70 líneas. Contiene: la regla de §3, cargar `i18n/<código>.yaml`, el
**fallo seguro** (sin catálogo: ejecutar en `es`, decirlo en una frase y añadir la
línea multilingüe de respaldo) y el aviso de IA en los tres idiomas. No se toca el
frontmatter.

**Precedencia, regla por regla:**

- La regla nueva prevalece sobre «rationale en español llano» (4.E) y sobre las
  plantillas en español **solo en el idioma de salida**.
- No prevalece sobre: S0–S5 y `<email-body-data>` como datos; el write-ahead de
  `registrar`; el fail-closed del modo rutina; que el modelo nunca vea el cuerpo crudo.
- Donde una regla fija un literal y otra manda traducir, se conserva la **función**: en
  `es` sale el literal exacto; en `en`/`fr`, su clave.
- Una prueba exige que la regla nombre esas precedencias y que no contenga «prevalece
  sobre todas las reglas».

## 7. Cobertura del aviso

El aviso de «traducción de IA, sin revisar» sale al principio de resumen, preguntas de
parada, errores y aviso de idioma desconocido. En este último va antes de la primera
sección, no como comentario final.

## 8. Verificación

1. **Línea base:** hash por línea de `SKILL.md`, `references/*.md`, `commands/triage.md`
   y `config.yaml` y comparación con `git show 2c98507:<fichero>`; lista `REEMPLAZOS`
   vacía; manifiestos comparados salvo la versión. Tras cada tarea, nada cambia fuera de
   los bloques delimitados.
2. **Pruebas nuevas** en `tests/`: una por fila de §3; cobertura de literales (todo texto
   visible es clave o instrucción declarada; bloques de código clasificados `salida` o
   `excluido`); validador de catálogos con catálogos rotos a propósito (mismas claves y
   marcadores, nada vacío ni `TODO`, textos contractuales idénticos, mismo número de
   opciones, texto igual al original solo si es `invariable`, un idioma sin revisor no
   puede ser `revisado`, glosario, `riesgo: alto` presente).
3. **Sabotaje** de las pruebas nuevas tras cada tarea importante; los mutantes que
   sobrevivan se cierran o se razonan. Las pruebas de frases literales se declaran de
   instantánea.
4. **Heurística de idioma:** si comparar palabras no discrimina entre `es`/`fr`/`en`, la
   prueba se omite de forma visible y se sustituye por marcadores ortográficos.
5. **Afirmaciones de estado vigiladas:** «ninguna traducción está revisada» tiene una
   prueba que obliga a retirarla si un catálogo pasa a `revisado`.
6. **CI:** job nuevo en `tests.yml` con validador, extractor y pruebas. El CI actual solo
   corre en PR y en `main`; mientras no haya PR, la verificación es local. Un check en rojo
   solo bloquea si el usuario activa la protección de rama exigiendo ese check por su
   nombre exacto, que se leerá del workflow.
7. **Empaquetado:** prueba, en copia temporal, de que el paquete incluye `i18n/*.yaml` y
   `scripts/idioma.py` y nada de `tests/`; se muestra `unzip -l`. La Release debe decir
   que hay que reinstalar el paquete completo.
8. **Versión:** `./scripts/bump-version.sh 3.14.0` y sección `## Novedades en v3.14.0`
   (Añadido / Cambiado / Limitaciones).

**Niveles de verificación que se declararán siempre por separado:** pruebas automáticas /
simulado con subagentes / ejecutado en la plataforma real. No habrá «verificado» de lo
que no se haya ejecutado en Claude Code o Cowork.

## 9. Revisión y simulación (Fase 7)

Revisión independiente de solo lectura de toda la rama, con mutaciones sobre una copia y
recuento por gravedad. Simulación con subagentes de contexto limpio que reciban el
paquete construido con el script real y un escenario pegado en el prompt; escenarios y
criterios preregistrados con ejemplo que pasa y ejemplo que falla (`en`, `fr`, idioma
no disponible, sin marca, `en` suelto, solo `SKILL.md` sin catálogos, dry-run, rutina,
parada). Tabla de registro para las ejecuciones reales pendientes.

## 10. Limitaciones conocidas (se documentarán)

- Traducciones escritas por una IA, sin revisión humana nativa ni de especialista.
- El texto libre que el modelo redacta (resúmenes, razones, notas) no está revisado.
- **La detección de inyección S0 solo cubre patrones en español e inglés, y esto NO
  cambia con este trabajo.** Es una propiedad del **idioma del correo recibido**, no del
  idioma de la interfaz: elegir `idioma=fr` solo traduce lo que el skill muestra; no
  añade patrones de detección en francés (ni en ningún otro idioma). Un correo hostil
  redactado en francés, o en cualquier otro idioma distinto de es/en, puede evadir S0
  con más facilidad. La defensa que sigue vigente en ese caso es el *escapado* mecánico
  y el hecho de que el modelo trata todo cuerpo como dato, no como instrucción. S0 ya era
  una lista de bloqueo *advisory best-effort* (ver CLAUDE.md). Ampliar los patrones es un
  pendiente ajeno, fuera de este trabajo. Esta aclaración se escribe en: README (sección
  Language / Langue y Limitaciones), CHANGELOG (Limitaciones), `i18n/README.md`,
  CLAUDE.md y AGENTS.md, y una prueba comprueba que cada uno la contiene.
- `fr` es el idioma que la IA que traduce juzga con menos seguridad.
- Los mensajes de error de los scripts siguen en español; el modelo los explica en el
  idioma elegido.
- Sin prueba en plataforma real (Claude Code / Cowork).

## 11. Pendientes ajenos (se anotan, no se tocan)

- `SKILL.md` dice «13 core» (l.160, 614) y «12 core» (l.1014).
- Ramas antiguas sin fusionar (`copilot/*`, `v2.0-improvements`).
- README completos en `en` y `fr`.

## 12. Riesgos y decisiones tomadas por el asistente

| Decisión | Coste si estaba mal |
|---|---|
| Marca `idioma=`/`lang=` en vez de argumento posicional | Menos elegante; cambiarla toca la tabla de §3 y sus pruebas |
| Reutilizar `usuario.idioma` | Usuarios que ya lo cambiaron verán ese idioma |
| Versión 3.14.0 | Bump distinto si se prefiere 3.13.6 |
| No tocar `triage_helpers.py` | Los mensajes de error siguen en español |
| Catálogos en YAML (no Markdown) | Revisar a mano es algo menos cómodo |
