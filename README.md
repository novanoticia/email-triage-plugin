# Email Triage Plugin v3.8.11

Filtrado epistémico de correo electrónico para Claude Cowork y Claude Code.

## Qué hace
Evalúa correos electrónicos usando un marco de racionalidad bayesiana inspirado en las [LessWrong Sequences](https://www.lesswrong.com/rationality): no "¿es importante?" sino "¿leer esto cambiaría algo concreto para mí?"

Analiza cada correo con 30 criterios epistémicos, genera una puntuación multi-eje (valor decisional, calidad epistémica, riesgo de manipulación, coste cognitivo, presión de acción) y clasifica en 4 tiers con una explicación legible de cada decisión.

## Filosofía
La mayoría de clasificadores de correo preguntan "¿es urgente?". Este plugin pregunta algo distinto:
- ¿Cambia una decisión? (Value of Information)
- ¿Actualiza mis predicciones? (Bayesian Surprise)
- ¿La evidencia es genuina o filtrada? (Filtered Evidence)
- ¿Explora o racionaliza? (Forward vs Backward Flow)
- ¿Es urgencia real o teatro? (Urgencia fabricada)
- ¿Está anclado a hechos verificables? (Entangled Truths)

El resultado no es un simple "urgente/no urgente" sino un filtro de: valor decisional, calidad epistémica, coste cognitivo y riesgo de manipulación.
## Novedades en v3.8.10

- **Corrección de un race TOCTOU en `compactar` (auditoría)**: `compactar` leía `correcciones.jsonl` **antes** de adquirir el `flock`, y solo bloqueaba después para reescribir. Entre esa lectura y el `os.replace`, un `registrar` concurrente (p. ej. una tarea programada mientras corre una sesión manual) podía añadir una corrección que quedaba **fuera** del conjunto reescrito y se perdía en silencio. Ahora `compactar` **relee bajo el lock** y recomputa las líneas a conservar, de modo que ningún append concurrente se pisa. El comentario del código ya prometía "bajo un flock para no pisar un `registrar` concurrente"; ahora el orden de ejecución lo cumple
- **Tests**: nuevo caso de regresión `test_append_concurrente_bajo_lock_no_se_pierde` que inyecta un append en el momento exacto de adquirir el lock y verifica que sobrevive (falla con el código antiguo, pasa con el arreglo) — suite total 89 tests

## Novedades en v3.8.9

- **Rotación de `correcciones.jsonl` (issue #1)**: nuevo subcomando `compactar` que recorta el historial a sus últimas N líneas (5000 por defecto, el mismo cap que ya usaba la lectura) de forma **atómica** (fichero temporal + `os.replace` bajo `flock`). El fichero era append-only sin purga; la lectura ya estaba acotada, ahora el disco también. Es no-op por debajo del tope y trae `--dry-run`
- **Mecanización del SCRIPT 3 de mover (issue #2)**: nuevo subcomando `montar-mover` que recibe cuenta, carpetas y las dos listas de message-ids y emite el **SCRIPT 3 completo con todo ya escapado** por `applescript_quote`. El modelo deja de ensamblar el literal `set toReview to {…}` a mano — que era el último borde donde los nombres de cuenta/carpeta podían quedarse sin escapar. Mecanismo, no confianza en el modelo
- **Tests**: 12 casos nuevos (recorte/no-op/dry-run de `compactar`; message-id hostil, salto de línea, carpeta con comilla, listas vacías y validación de `montar-mover`) — suite total 88 tests

## Novedades en v3.8.8

- **Paridad de blindaje en la ruta de `scoring`**: si el usuario invocaba `scoring` con un `config.yaml` sintácticamente roto sin correr antes `validar-config`, `_cargar_config` reventaba con un traceback crudo (el resto del pipeline ya degradaba con guardas de forma). Ahora captura el YAML roto / fichero ilegible y devuelve el mismo contrato `{"ok": false, "error", "linea", "columna"}` que el resto de subcomandos, por stdout
- **Escapado de nombres de cuenta/carpeta en AppleScript (defensa en profundidad)**: el helper `escapar-applescript` ya existía para los message-ids, pero el SKILL solo lo aplicaba a esos. Ahora documenta escapar también `NOMBRE_CUENTA`/`CARPETA_*` y los placeholders `<<CUENTA>>`/`<<ORIGEN>>`/`<<DESTINO_*>>`: salen del propio `config.yaml` (no es inyección remota), pero una comilla en un nombre de carpeta rompía igual el literal y abortaba el mover
- **Dependencia declarada**: nuevo `requirements.txt` con `PyYAML` (lo usan `scoring` y `validar-config`); el resto del plugin sigue siendo stdlib-only
- **Tests**: 4 casos nuevos para la ruta de `scoring` blindada (YAML roto, config ilegible, config válido, YAML vacío) — suite total 76 tests

## Novedades en v3.8.7

- **`.mcp.json` conforme al esquema de plugin**: el fichero declaraba el proveedor de correo con una estructura propia (`email`/`options`) que Claude Code no interpreta —el esquema esperado es `{"mcpServers": {...}}`—, así que no registraba nada. Ahora declara explícitamente que el plugin no empaqueta ningún servidor MCP (`{"mcpServers": {}}`): iCloud usa AppleScript y el conector de Gmail lo añade el usuario desde Claude/Cowork (documentado en README y SKILL). Evita además forzar una conexión a Gmail a quien solo usa iCloud
- **`scoring.ejes` mal formado ya no revienta el scoring**: un eje del `config.yaml` con forma inesperada (`valor_decisional: 5` en vez de `[0, 10]`) hacía saltar `lo, hi = rangos[nombre]` con `ValueError`/`TypeError`. Ahora el eje se deja sin clampar y se reporta en `ignorados`, y `validar-config` lo avisa antes de operar. Era la última entrada del pipeline sin guarda de forma
- **Tests**: nuevos casos que fijan ambos comportamientos (eje malformado en `scoring` y en `validar-config`)
- **Limpieza**: `.gitignore` tenía el bloque `email-triage-fix/` / `*.patch` / `APLICAR.md` / `ISSUE-*.md` duplicado; se deja una sola vez

## Novedades en v3.8.6

- **Verificación de integridad de la instalación (#12)**: `install-plugin.sh` comprueba al final los 9 ficheros del skill y avisa —sin abortar— si el árbol quedó incompleto (típicamente `references/mail-consolidado.applescript`, la vía canónica del PASO 1). Antes, una instalación parcial degradaba en silencio al fallback manual S0–S5; ahora lo dice. Una instalación sana no añade ruido.

## Novedades en v3.8.5

Verificación de una auditoría externa (Mistral) contra el código real: de sus 13 hallazgos+riesgos, solo 4 resultaron ciertos y accionables; el resto ya estaba cubierto (homóglifos en asunto/remitente, tests de `escapar-applescript`, aviso de eje inválido, limpieza de `tmp/`…) o partía de premisas incorrectas. Se aplican los confirmados:

- **`ajustes` y `validar-config` sobreviven a un fichero ilegible**: un `PermissionError` (o E/S rota) en `correcciones.jsonl` / `config.yaml` tumbaba el subcomando con un traceback crudo. Ahora `ajustes` degrada a "sin ajustes aprendidos" reportando `error_lectura`, y `validar-config` devuelve `ok: false` con motivo legible. La lectura del JSONL pasa además a `errors="replace"`: una línea con bytes ilegibles ya no aborta la pasada entera
- **Guardas de forma en `scoring`**: un payload que no es objeto JSON, un item de lote no-objeto, un `verdicts` no-objeto, un veredicto no escalar (lista/dict), un `extra_points` no numérico o un YAML vacío (`safe_load` → `None`) reventaban con `AttributeError`/`TypeError`. Ahora devuelven error legible o entran en `ignorados`, y un item malo **no tumba el resto del lote**
- **`validar-config` detecta claves booleanas** (`si:`/`no:` sin comillas, la trampa YAML 1.1 del gotcha del CLAUDE.md): paridad runtime con el gate #2 del CI, que solo vigila la plantilla del repo — no el `config.yaml` real del usuario
- **`escapar-applescript` marca longitudes >998** (límite de línea de cabecera RFC 5322) como `sospechosos`, con campo `motivo` explícito. Nota: el "límite de 255 caracteres de AppleScript" que alegaba la auditoría no existe en AppleScript moderno (era el `Str255` clásico); el escape ya neutralizaba estos valores, esto añade la señal
- **16 tests nuevos** (70 en total) fijan todo lo anterior, incluido el caso prometido en v3.8.2 y nunca testado: stdin con bytes no-UTF8 por subprocess
- **La cabecera versionada de `triage_helpers.py` entra en la disciplina de versión**: derivaba en silencio (decía v3.8.2 en un plugin v3.8.4) porque ni `bump-version.sh` ni el CI la vigilaban. Ahora es el 8º sitio del bump y el gate #3 del CI la valida

## Novedades en v3.8.4
Release de *hardening* a partir de una auditoría de las **superficies de metadatos**: el saneo S0 protegía cuerpo y asunto, pero dos metadatos igualmente controlados por quien envía el correo se le escapaban. **8 tests nuevos** (la batería sube de 46 a 54). Sin cambios en el comportamiento normal del scoring.
- **`escapar-applescript` — el `message-id` deja de ser un vector de inyección**: el `message id` es una cabecera del correo (controlada por el remitente) y NO pasaba por S0. Interpolado crudo en el literal del script de mover (`set toReview to {"<mid>", ...}`), un message-id con una comilla cerraba la cadena y AppleScript ejecutaba lo que siguiera (`& (do shell script "...")`). Nuevo subcomando de `triage_helpers.py` que valida y escapa cualquier valor y devuelve la lista AppleScript ya montada; PASO 1 del `SKILL.md` y el SCRIPT 3 lo promueven a vía obligatoria
- **El nombre del remitente también pasa por S0 (`sanitizar --remitente`)**: el display-name de la cabecera `From` es texto libre del atacante y llegaba al contexto como metadato "de confianza". Ahora se escanea con S0, capa el tier a `REVIEW` igual que el asunto y expone `remitente_evaluable` (vacío si contenía inyección)
- **Defensa en profundidad, no confianza en el modelo**: ambos huecos se cierran con un mecanismo (escape/saneo), no con una instrucción que el modelo deba recordar. La `CLAUDE.md` añade la invariante correspondiente
- **Tests**: la batería sube a **54** (escapado del payload de breakout, remitente inyectado que capa el tier, y las guardas de entrada)

## Novedades en v3.8.3
Cierra los tres issues abiertos del repo (#4, #5, #6) y añade guía de co-creación para agentes.
- **Un solo comando para el bump de versión (#5)**: `scripts/bump-version.sh X.Y.Z` actualiza los **7 sitios** de versión de una pasada (5 semver + cabecera de `config.yaml` + H1 del `SKILL.md`) y valida con el mismo criterio del CI. De paso arregla un *drift* real: el H1 del `SKILL.md` seguía en `v3.4` en un plugin v3.8. El gate de CI ahora **también** vigila el H1, así que no puede volver a derivar
- **Instalación en Cowork desacoplada del rpm (#4)**: `install-plugin.sh` ya no parchea por defecto la copia efímera del plugin en la sesión de Cowork; la vía canónica es el **marketplace**. El parcheo del rpm queda como flag opt-in `--cowork` (o `PATCH_COWORK_RPM=1`) en `fix-cowork-version.sh`. La sincronización de la caché de Claude Code sigue por defecto
- **CI: guardia contra duplicación de scripts (#6)**: un paso nuevo falla el build si `triage_helpers.py` / `test_triage_helpers.py` aparece en más de una ruta, o si reaparece el árbol paralelo `plugins/email-triage/scripts/` (que Cowork empaquetaría en vez del canónico)
- **`CLAUDE.md`**: guía de co-creación en la raíz (objetivo, arquitectura mecánico-vs-juicio, cómo correr los tests, invariantes de seguridad, disciplina de versión y mapa de ficheros) para que un agente entienda el repo sin adivinar

## Novedades en v3.8.2
Release de *hardening* a partir de una segunda auditoría externa, esta vez **verificada contra el código real** (no solo el README) caso por caso. Cuatro correcciones y **9 tests nuevos** (la batería sube de 37 a 46). Sin cambios en el comportamiento normal del scoring.
- **Append concurrente-seguro (`registrar`)**: nuevo subcomando de `triage_helpers.py` que añade líneas a `correcciones.jsonl` / `session_log.jsonl` con **lock de fichero** (`fcntl.flock`) y newline garantizado. Cierra el riesgo de que dos sesiones simultáneas —p. ej. una tarea programada y una manual— entrelacen líneas y corrompan el JSONL. El PASO 4.I del `SKILL.md` lo promueve a vía canónica; `write_file` queda como *fallback*
- **S0 cubre homóglifos de otros alfabetos**: nueva *vista desconfundida* que mapea confusables cirílicos/griegos a latín antes de aplicar los patrones. Ahora se detecta `ignоre` con la `o` cirílica (U+043E) o la `ο` griega (U+03BF), hasta ahora un límite conocido. Es solo-para-detección: correo multilingüe legítimo (ruso, griego) **no** genera falsos positivos, porque solo salta si el texto desconfundido imita una instrucción
- **`validar-config` detecta el fallo silencioso de estructura**: avisa de criterios activos **sin `eje`** (o con un `eje` inexistente en `scoring.ejes`), que en el modo determinista pierden sus puntos sin avisar. Es el modo de fallo real cuando un config antiguo sobrevive a un cambio de estructura (p. ej. el mapeo criterio→eje de v3.6)
- **Robustez de entrada**: la lectura de `stdin` en `sanitizar` tolera bytes no-UTF8 (un cuerpo en ISO-8859-1 ya no rompe el pipe); test explícito de cuerpo vacío; el directorio de telemetría se crea con `mkdir -m 700` (cierra la ventana entre `mkdir` y `chmod`)

## Novedades en v3.8.1
Release de mantenimiento y *hardening*, surgido de una auditoría externa del repo (verificada caso por caso, sin cambios en el comportamiento normal del scoring). Cuatro correcciones y un test nuevo.
- **Vía de lectura segura como opción principal (iCloud)**: PASO 1 del `SKILL.md` promueve el script consolidado (`references/mail-consolidado.applescript`) a vía canónica y nombrada — metadatos por stdout, cuerpos crudos a `~/.email-triage/tmp/tbody_N.txt` en `700`, sanitizados **antes** de llegar al modelo. El listado inline que volcaba los cuerpos crudos al contexto queda como *fallback* con aviso explícito. Cierra la incoherencia entre el flujo documentado y la promesa de «el modelo solo ve texto ya filtrado», y añade una regla no negociable en PASO 1 y PASO 1.B que prohíbe exponer un cuerpo crudo sin sanitizar
- **Permisos del directorio de telemetría**: `install-plugin.sh` fija `~/.email-triage/` a `700` siempre (también sobre directorios preexistentes de versiones anteriores). Guarda asuntos y remitentes en JSONL con retención indefinida; en una Mac multiusuario no deben quedar world-readable. Complementa el `700` que ya tenía el subdirectorio `tmp/`
- **`fix-cowork-version.sh` a prueba de destino equivocado**: guarda estructural antes del `cp -r` (confirma que el destino hallado por `find` es de verdad la raíz de este plugin) y copia *best-effort* que nunca aborta la instalación. El parcheo del rpm de Cowork queda documentado como apaño de conveniencia frente a la vía marketplace
- **Cap de lectura en `cmd_ajustes` (PASO 0.B)**: `correcciones.jsonl` es append-only y crece sin límite; ahora se leen solo las últimas 5.000 líneas vía `deque(maxlen)` (memoria acotada sea cual sea el tamaño; *escape hatch* con `max_lineas<=0`). Se preserva la semántica de `correcciones_totales`
- **Tests**: la batería sube a **37** (nuevo test del cap de lectura: tope respetado y lectura completa con el tope desactivado)

## Novedades en v3.8

Nuevo **modo veloz** (opt-in): un perfil de bajo consumo de tokens y menor
latencia, pensado para el barrido diario rápido frente a la revisión semanal
a fondo. Es un **pre-filtro de ruido**, no el evaluador a fondo de 30 criterios.

- **Modo veloz (`config-veloz.yaml`)**: capa de overrides que se superpone al `config.yaml` normal solo durante la sesión, sin tocar perfil, cuenta ni carpetas. Se activa diciendo "triaje veloz" en el chat (o con `scoring.perfil: veloz`). Recorta a los 12 criterios *core*, fuerza scoring **determinista** en lote (`--brief`), salta la calibración y la verificación contra Enviados, acorta el cuerpo leído (800 car.) y reduce la explicación a 1+1 razones sin rationale
- **Ahorro estimado**: ~45–60 % de tokens por sesión (~50 correos) frente al perfil por defecto, a cambio de menos matiz. Compatible con `simulacion` y `rutina`
- **Documentación**: nueva sección *Modo veloz* en Configuración y plantilla `config-veloz.yaml` en `skills/email-triage/`

## Novedades en v3.7.2
Release de mantenimiento: dos guardas de validación de entrada (sin cambios en el comportamiento normal del scoring), surgidas de una revisión externa verificada caso por caso.
- **`max_chars` no positivo ya no destroza el cuerpo**: en `cmd_sanitizar`, un `max_caracteres_cuerpo` / `--max-chars` con valor `0` vaciaba el cuerpo (`texto[:0]`) y un negativo lo cortaba por el final (`texto[:-n]`). Ahora un valor no entero o ≤0 cae al presupuesto por defecto documentado (1500)
- **Una hard rule mal configurada ya no tumba el scoring**: en `_aplica_hard_rules`, un valor no numérico en `hard_rules` (p. ej. `pregunta_directa_boost: "alto"`) lanzaba `TypeError`. Ahora se registra en `ignorados` con su motivo y el scoring continúa
- **Type hints** en las funciones públicas (`cmd_ajustes`, `cmd_sanitizar`, `cmd_scoring`, `cmd_scoring_dispatch`, `cmd_validar_config`)
- **Tests**: la batería sube a **34** (2 nuevos que fijan ambas guardas)

## Novedades en v3.7.1
Release de mantenimiento sobre la 3.7.0: un bug real con causa rastreable más limpieza de fontanería y de release. No cambia el comportamiento del scoring.
- **Fix del fallback de config (regresión del `git mv` `bbc1019`)**: en modo determinista, si no existía el `config.yaml` del usuario, `_cargar_config` construía una ruta con un nivel `skills/email-triage` de más y reventaba con `FileNotFoundError` en vez de caer a la plantilla del plugin —justo la red de seguridad que aquel commit pretendía garantizar—. Ahora resuelve `../config.yaml` y, si tampoco existe, devuelve un error legible en lugar de un traceback
- **Coherencia de versiones blindada en CI**: el frontmatter de `SKILL.md` (3.6.0) y la cabecera de `config.yaml` (v3.4) se habían quedado rezagados respecto a `plugin.json`/`marketplace.json`. Sincronizados a 3.7.1, y un nuevo paso de CI falla el build si los 5 sitios de versión completa divergen o si la cabecera de config no cuadra en major.minor
- **Instalador duplicado eliminado**: había dos `install-plugin.sh` (raíz y `scripts/`) ya divergidos; el canónico es `scripts/` (el que descarga el README), así que se borra la copia muerta de la raíz
- **AppleScript más higiénico**: la escritura de `/tmp/tbody_N.txt` va envuelta en `try` (cierra el handle ante un fallo de E/S) y se limpian los cuerpos crudos de ejecuciones previas, más una plantilla de limpieza documentada (SCRIPT 4) para no dejar contenido de correo en `/tmp`
- **Tests**: la batería sube a **32** (2 nuevos que fijan el fallback de `_cargar_config`, sin cobertura hasta ahora)

## Novedades en v3.7
Parche de 5 correcciones sobre el scoring determinista de v3.6, surgido de una sesión real de triaje que destapó los fallos en vivo.
- **REPLY_NEEDED exige señal de acción, no score alto**: el fallo más visible era que un correo de mucho valor informativo (una newsletter de tips) llegaba a `REPLY_NEEDED` solo por sumar `score ≥ 10`. "Muy valioso para leer" ≠ "exige tu respuesta". Ahora REPLY_NEEDED solo se alcanza con `forzar_reply_needed` (pregunta directa, deadline ≤72h, hilo bloqueado); el score/urgencia por sí solos topan en REVIEW. Matiz que descubrió el test: `presion_accion` **no** sirve de gate, porque `impacto_causal_real` se le suma y un correo puede tener impacto sin pedir respuesta. Configurable en `scoring.cap_reply_needed_sin_accion`
- **`sender_bulk` atenuado para remitentes que conservas**: la penalización de "remitente masivo" (−4) aplastaba newsletters intelectuales que el usuario guarda a mano (el premio por dominio frecuente era solo +1). Con `remitente_en_historial: true` la penalización pasa a `scoring.sender_bulk_atenuado_a` (−1 por defecto)
- **Scoring en lote + `--brief`**: `scoring` acepta `{"emails":[...]}` (1 parse de YAML para todo el lote) y el flag `--brief` devuelve solo `{id, score, tier, ejes, cap_aplicado?}`. Volcar los ~18 criterios por correo era el mayor gasto de tokens; el desglose completo se guarda en telemetría, no en contexto
- **Nuevo subcomando `validar-config`**: parsea el `config.yaml` y devuelve `ok` o `error`+`linea`/`columna`. Motivo: un config con una clave mal indentada tumbaba el modo determinista con un traceback en vez del fallback "mental". Se ejecuta al inicio de PASO 0
- **Mail más robusto**: plantillas consolidadas (`references/mail-consolidado.applescript`) que leen metadatos+cuerpos en una sola pasada (menos round-trips a osascript, ~60 s cada uno), mueven por `whose message id is` (evita el `-1728` al iterar durante la sincronización) y **verifican por conteo** en vez de fiarse del valor de retorno de AppleScript; crear buzones se separa de mover
- **Tests**: la batería sube a **30** (cap de REPLY_NEEDED, REPLY_NEEDED solo con señal de acción, atenuación de `sender_bulk`, lote/brief). El contrato del test de tier se actualizó al nuevo comportamiento

## Novedades en v3.6
- **Scoring determinista opt-in**: el modo de agregación del score es ahora configurable (`scoring.modo`). Por defecto sigue en **mental** (el modelo agrega los ejes con su juicio, comportamiento idéntico al anterior). Activando **determinista** —en el config o diciéndolo en el chat— el modelo solo evalúa cada criterio y `triage_helpers.py scoring` hace la aritmética: suma por eje, **clampa** cada eje a su rango, añade hard rules y el cap por inyección, y devuelve `score`+`tier` reproducibles. Pensado para auditar una sesión o comparar cambios de pesos
- **Campo `eje` en los 30 criterios**: cada criterio declara a qué eje (`valor_decisional`, `calidad_epistemica`, `riesgo_manipulacion`, `coste_cognitivo`, `presion_accion`) contribuye, y el bloque `scoring.ejes` fija sus rangos. Es la fuente única del mapeo criterio→eje que usa el modo determinista; editarlo no toca código
- **Instalador endurecido**: rescata el `config.yaml` editado de instalaciones v3.3 **antes** del `git reset --hard` que lo destruía; lectura de versión vía `sys.argv` (sin interpolar rutas en Python); y los mensajes dicen «fetch + reset --hard», que es lo que el script hace de verdad
- **Tests**: la batería sube a 27 (7 nuevos para el scoring determinista: suma por eje, clamp, hard rules, veredictos inválidos, cap por inyección)

## Novedades en v3.5
- **El asunto también se sanitiza**: el detector de prompt injection (S0) se aplica ahora al asunto además del cuerpo. Tiene sentido porque el asunto alimenta hard rules de peso (+4 pregunta directa, +4 deadline, +3 mención), así que es una vía de ataque tan real como el cuerpo. Si el asunto contiene patrones de manipulación, se descarta y se evalúa solo por remitente y fecha
- **Cap de tier ante inyección**: un correo con inyección detectada (en cuerpo o asunto) **no puede recibir `REPLY_NEEDED` automáticamente** — su tier máximo es `REVIEW`. Un atacante controla los metadatos que suman puntos, así que un humano debe ver el correo antes de que el sistema lo declare urgente. Siempre puedes subirlo a mano, y esa corrección alimenta el feedback loop
- **Hilos «esperando respuesta» verificados de verdad**: antes el +5 de «el usuario es el blocker» se aplicaba casi siempre, porque la señal era invisible (tus propios envíos viven en Enviados, no en la bandeja triada). Ahora la señal tiene tres estados —`true`/`false`/`desconocido`— confirmados contra la carpeta de Enviados en iCloud, o leídos del hilo nativo en Gmail. El **+5 solo se aplica con `false` confirmado; +2 si es incierto; 0 si ya respondiste**
- **Gmail usa el hilo nativo (`threadId`)**: en lugar de la heurística de asunto+participante, se agrupa por el hilo real de Gmail (más fiable, e incluye tus respuestas). La heurística queda solo para iCloud/Mail.app
- **Log de sesión append-only**: el registro para el undo ya no edita líneas escritas (era frágil y podía corromper justo el archivo que permite revertir). Fallos y reversiones se anotan como eventos nuevos; el undo solo lee. La purga de entradas antiguas (>30 días) se hace al cerrar la sesión, nunca durante un undo
- **Truncado del cuerpo unificado**: dos únicos números en orden claro — extracción cruda generosa (4000 caracteres) y luego presupuesto final `puntuacion.max_caracteres_cuerpo` aplicado **sobre el texto ya limpio**. Antes se truncaba en corto *antes* de limpiar, lo que destrozaba los correos HTML. La plantilla sube su valor por defecto a 1500
- **Correcciones de dry-run ponderadas**: los overrides hechos durante una simulación se registran con `simulacion: true` y pesan la mitad en el aprendizaje, para no contaminar el perfil de producción con pruebas de umbrales
- **Integración continua**: los cambios en Python se validan con una batería de tests (`skills/email-triage/scripts/test_triage_helpers.py`) que corre en GitHub Actions en cada push

## Novedades en v3.4
- **Config personal persistente**: vive en `~/.email-triage/config.yaml`, fuera del repo — sobrevive a las actualizaciones (`git reset --hard`) y no puede filtrarse a git. El `config.yaml` del repo pasa a ser solo plantilla
- **Lógica determinista en `skills/email-triage/scripts/triage_helpers.py`**: el decay y la agregación de correcciones (PASO 0.B) y la sanitización del cuerpo (S0–S5) se ejecutan ahora en Python, no como aritmética mental del modelo. La defensa anti-injection pasa de instrucción a mecanismo: el modelo solo ve texto ya filtrado. El procedimiento manual del SKILL.md queda como fallback
- **`/triage` dentro del plugin**: el comando se carga desde `plugins/email-triage/commands/`
- **Versiones unificadas**: plugin.json como fuente de verdad, con aviso de deriva en `fix-cowork-version.sh`

## Novedades en v3.3
- **Modo rutina (scheduled task)**: nuevo bloque `interaccion.rutina` en `config.yaml` que sobrescribe `interaccion.modo` cuando el skill se invoca desde una rutina programada (etiqueta `<scheduled-task>` en el contexto)
- **Silencioso con umbral**: en rutina, mueve solo lo claramente actionable (score ≥ `umbral_mover`) y lista como **candidatos dudosos** lo que está entre `umbral_dudoso_min` y `umbral_dudoso_max` para revisión humana posterior
- **Notificación macOS al terminar**: lanza `display notification` vía osascript con resumen breve ("N movidos, M dudosos en T min"), sonido configurable
- **Timestamps automáticos**: marca hora de inicio en la primera línea y hora de fin antes del resumen, con duración total
- **Cero preguntas en rutina**: el modo está diseñado para ejecuciones desautendidas; cualquier ambigüedad se resuelve autónomamente y se nota brevemente en el resumen
- **Compatible con `simulacion`**: si la rutina se ejecuta en dry-run, notifica los movimientos hipotéticos sin tocar nada

## Novedades en v3.2
- **Modo dry-run (simulación)**: previsualiza el triaje sin mover nada — propaga como flag por PASO 0/4.G/5, con resumen agregado al final
- **Sanitización de entrada**: PASO 1.B normaliza HTML/base64/caracteres de control y detecta payloads de prompt injection antes de scoring
- **Defensa prompt injection (3 capas)**: delimitadores `<email-body-data>`, detector S0 sobre el cuerpo sanitizado, framing como *datos no instrucciones* (ampliado en v3.4.1 con doble vista crudo/decodificado, en v3.5 al asunto y con normalización Unicode —NFKC + strip de caracteres invisibles— contra evasión por ancho cero/fullwidth). Es una defensa **heurística**: reduce el riesgo, no lo elimina. Un payload novedoso o con homóglifos de otro alfabeto puede evadir S0; por eso el correo con inyección se capa a `REVIEW` y lo revisa un humano
- **Detección de hilos**: PASO 1.C normaliza `Re:`/`Fwd:` y cruza participantes; PASO 4.J aplica peso al hilo completo en lugar de scoring mensaje a mensaje
- **Undo / rollback**: PASO 4.I escribe log de sesión y PASO 6 permite deshacer el último batch movido
- **Feedback loop**: PASO 0.B lee reglas aprendidas del historial; PASO 4.A las aplica con decaimiento temporal
- **Telemetría persistente real**: PASO 5.B escribe JSONL en `~/.email-triage/` (antes la telemetría nunca tocaba disco)
- **Instalador reescrito**: instala en `~/.claude/plugins/marketplaces/`, lee versión dinámicamente, chequea dependencias, crea directorio de sesión

## Novedades en v3.1
- Indicadores de color por tier
- Patrón seguro de movimiento en lote
- Soporte UTF-8 en nombres de carpeta
- Validación de contenido HTML
- Carpeta destino para reply_needed

## Novedades en v3.0
- 30 criterios epistémicos
- Scoring multi-eje
- 4 tiers de routing
- Explicación obligatoria
- Hard rules expandidas
- Telemetría

## Requisitos

- **`git` y `python3`** en el `PATH` (Python 3.9+).
- **PyYAML** — necesario **solo** para el subcomando `scoring` del modo
  *determinista* (`scripts/triage_helpers.py scoring`). Sin él, el skill
  detecta la ausencia y cae automáticamente al **modo mental** (sin romperse),
  pero el scoring deja de ser reproducible por script. Instálalo con:

  ```bash
  python3 -m pip install --user pyyaml
  # En entornos con PEP 668 ("externally-managed-environment"):
  python3 -m pip install --break-system-packages pyyaml
  ```

  Verifica con `python3 -c "import yaml; print(yaml.__version__)"`. Instálalo
  para el **mismo** `python3` que ejecuta el skill (en macOS suele ser
  `/usr/bin/python3`; comprueba con `which -a python3`).

- **macOS — permiso para instalación automática**: si dejas que Claude/Cowork
  instale PyYAML por ti (en lugar de ejecutar tú el `pip` de arriba), macOS
  pedirá autorización. Debes concederla en **Ajustes del Sistema → Privacidad
  y seguridad** (control de la app/Terminal e instalación de paquetes); fue
  necesario habilitarlo para que el asistente pudiera instalar dependencias.
  Si prefieres no dar ese permiso, instala PyYAML **a mano** con el comando
  anterior: es la única dependencia externa.

## Instalación

El proceso tiene **dos pasos obligatorios** tanto en instalación como en
actualización: (1) sincronizar los archivos del repo localmente y
(2) registrar/refrescar el plugin desde la interfaz gráfica de la app.

> ⚠️ **Importante**: el script `install-plugin.sh` solo prepara los archivos
> en disco. Claude Code y Cowork **no detectan el plugin ni la nueva versión**
> hasta que pasas por **"Explorar plugins"** y haces clic en "+" (instalación)
> o desactivas/reactivas (actualización). Saltarse el paso 2 es la causa más
> común de "instalé la nueva versión pero sigue saliendo la antigua".

### Paso 1 — Sincronizar el repo local

**Opción A (recomendada): script automatizado.**

```bash
curl -O https://raw.githubusercontent.com/novanoticia/email-triage-plugin/main/scripts/install-plugin.sh
chmod +x install-plugin.sh
./install-plugin.sh
```

El script clona en `~/.claude/plugins/marketplaces/email-triage-plugin/`,
lee la versión desde `plugin.json`, sincroniza la caché y crea
`~/.email-triage/` para logs de sesión y telemetría. En instalaciones
existentes hace `git fetch` + `reset --hard origin/main`. Requiere
`git` y `python3` en `PATH`.

> **Cowork (v3.8.3)**: el instalador ya **no** parchea por defecto la copia
> efímera del plugin dentro de la sesión de Cowork (el *rpm*) — es una ruta
> que no controlas y cuyo layout puede cambiar. La vía canónica en Cowork es
> el **marketplace** (Paso 2). Si necesitas forzar el parcheo del rpm de la
> sesión actual, pásale el flag opt-in: `./install-plugin.sh --cowork`.

**Opción B: manual.** Clona el repo en
`~/.claude/plugins/marketplaces/email-triage-plugin/` (para actualizar,
`git fetch origin && git reset --hard origin/main`, que es lo que hace
la opción A).

### Paso 2 — Registrar / refrescar en la app (obligatorio)

Tanto en **Claude Code** como en **Cowork**:

1. Abre **"Personalizar" → "Explorar plugins"**.
2. Busca **"Email-triage-plugin"** en la sección **"Personal"**.
3. Según el caso:
   - **Primera instalación**: haz clic en **"+"** para añadirlo.
   - **Actualización a nueva versión**: haz clic en **"Gestionar"**,
     **desactívalo** y vuelve a **activarlo** para forzar la
     resincronización de versión. Sin este paso la app seguirá usando
     la versión cacheada anterior, aunque el repo local ya esté en
     la nueva.

## Configuración
Desde v3.4 tu config personal vive en `~/.email-triage/config.yaml`
(el instalador lo crea desde la plantilla si no existe). Edítalo ahí
antes del primer uso — **no** edites el `config.yaml` de dentro del
repo: es solo la plantilla y se sobrescribe en cada actualización.

### Actualizar cuando cambia la estructura del config

El instalador **preserva** tu `~/.email-triage/config.yaml`: no lo
sobrescribe en las actualizaciones, para no perder tus ajustes. Eso tiene
una contrapartida importante que conviene tener clara como norma general:

> **Siempre que una versión cambia la _estructura_ del `config.yaml`**
> (campos o bloques nuevos, claves renombradas), tu config antiguo se queda
> desincronizado con la plantilla nueva — al respetarlo, el instalador **no**
> le añade los campos nuevos. Tu config viejo sigue siendo válido para lo que
> ya tenía, pero le faltan las piezas nuevas.

Por qué importa: algunas funciones leen tu config externo y dependen de esos
campos. Ejemplo real de v3.6: el **modo determinista** necesita el campo
`eje:` en cada criterio y el bloque `scoring`; con un config anterior a v3.6
esos campos no existen, así que el scoring determinista ignoraría criterios y
devolvería 0 — un fallo silencioso, difícil de diagnosticar.

**Procedimiento recomendado** cuando las notas de versión indiquen un cambio
de estructura del config (las migraciones de datos —`correcciones.jsonl`,
logs— NO se ven afectadas; esto es solo el `config.yaml`):

1. **Backup** del config actual:
   ```bash
   cp ~/.email-triage/config.yaml ~/.email-triage/config.backup-$(date +%Y%m%d).yaml
   ```
2. **Elimina** el config existente para que el instalador regenere uno limpio
   desde la plantilla nueva (recuerda: solo lo crea si **no** existe):
   ```bash
   rm ~/.email-triage/config.yaml
   ```
3. **Reinstala / actualiza** y vuelve a introducir tus datos personales
   (`usuario`, `correo`, `carpetas`, `filtros`, umbrales…) en el config fresco
   — a mano comparando con tu backup, o pidiéndoselo a la IA con el backup
   delante. Así obtienes la estructura nueva **con** tus datos de siempre.

### Campos básicos
- `usuario`: nombre, perfil profesional, proyectos activos
- `correo`: proveedor (icloud/gmail/otro), nombre de cuenta
- `carpetas`: bandeja, pendiente, destino, historial

### Modos de interacción
- `confirmacion`: pregunta uno a uno (recomendado al inicio)
- `lote`: presenta todos y pide confirmación global
- `silencioso`: mueve automáticamente (tras validar el criterio)
- `simulacion`: dry-run, no mueve nada (también activable diciendo "simula" / "qué movería")
- **rutina** (v3.3): se aplica cuando el skill se ejecuta desde una scheduled task **y** `interaccion.rutina.activo` está en `true`. Desde v3.4.3 viene en `false` por defecto (opt-in consciente): una plantilla recién instalada no mueve correo de forma desatendida hasta que tú lo decides. Configura el bloque `interaccion.rutina` para umbral de movimiento, candidatos dudosos y notificación macOS.

### Configuración del modo rutina
```yaml
interaccion:
  modo: "confirmacion"           # modo manual habitual
  rutina:
    activo: false                # true para respetar este bloque en scheduled tasks (opt-in desde v3.4.3)
    modo: "silencioso"
    umbral_mover: 10             # score mínimo para mover
    umbral_dudoso_min: 4         # rango de "dudosos" (no se mueven)
    umbral_dudoso_max: 9
    archivar_automaticamente: false
    notificacion_macos: true
    sonido_notificacion: "Glass"
    incluir_timestamps: true
```

Instrucción recomendada para la scheduled task:
```
Ejecuta el skill `email-triage` siguiendo el bloque
`interaccion.rutina` del config.yaml. Marca timestamps de
inicio/fin. Al terminar, envía notificación de macOS con
resumen breve. Decide autónomamente cualquier ambigüedad.
```

### Modo veloz

Perfil **opt-in** de bajo consumo de tokens y menor latencia, a costa de matiz.
Es un *pre-filtro de ruido* (barrido diario rápido); para la revisión cuidadosa,
usa el config normal.

**Activación**
- Por chat: di "triaje veloz" o "modo veloz".
- Por config: `scoring.perfil: veloz` en `~/.email-triage/config.yaml`.

Al activarse, además del `config.yaml` normal (perfil, cuenta, carpetas, filtros),
se carga la capa `config-veloz.yaml` —plantilla en `skills/email-triage/`; cópiala
a `~/.email-triage/config-veloz.yaml` para usarla— que superpone estos ajustes
**solo durante la sesión**:

| Ajuste | Veloz | Por defecto |
|---|---|---|
| Criterios evaluados | 12 *core* | hasta 30 |
| Scoring | determinista + `--brief` | mental |
| Calibración | se omite / reutiliza | cada sesión |
| Verificación contra Enviados | se omite | activa |
| Cuerpo leído | 800 car. | 1500 car. |
| Explicación | 1+1 razones, sin rationale | 3+3 + rationale |

Ahorro típico estimado: **~45–60 % de tokens** por sesión (~50 correos).
Compatible con `simulacion` y `rutina`.

### Tiers y umbrales
- `tiers`: umbrales configurables para cada tier
- `hard_rules`: puntos fijos por señales deterministas

## Troubleshooting
### "Plugin validation failed" al instalar el ZIP en Cowork
El validador del backend de Anthropic rechaza archivos `.yaml` dentro de plugins subidos por ZIP. Usa el flujo de instalación automatizada o manual.

### "Mail.app no responde" o timeout en osascript
Mail.app debe estar abierto para que el skill acceda al correo. Verifica en Ajustes del Sistema → Privacidad y Seguridad → Automatización que Claude/Cowork tenga permiso para controlar Mail.app.

### "No puedo acceder a Gmail" o conector no disponible
Verifica que el conector Gmail MCP esté activo en Configuración → Conectores de Cowork. Si el token ha expirado, desconéctalo y vuelve a conectar.

### Carpeta no encontrada
Los nombres de carpeta en `config.yaml` deben coincidir exactamente con los de tu cliente de correo (incluyendo mayúsculas).

### El triaje parece impreciso
Asegúrate de que `usuario.perfil` en `config.yaml` describa bien tu rol e intereses.

### Correos muy largos causan lentitud
Reduce `puntuacion.max_caracteres_cuerpo` (presupuesto del cuerpo ya limpio; 800 para priorizar velocidad) o desactiva `leer_cuerpo` si prefieres rapidez sobre precisión. La extracción cruda previa (4000) la fija el SKILL y no se toca aquí.

## Decisiones de diseño

Esta sección recoge las decisiones de fondo del plugin: no *qué* hace cada
versión (eso está en las «Novedades»), sino **por qué** se eligió un camino y
qué alternativas se descartaron (al menos de momento). Las decisiones de v3.6
se tomaron de forma explícita y discutida; las anteriores están reconstruidas
a partir del registro del repo (Novedades, commits, comentarios del código),
así que su *racional* es una lectura razonada del rastro documentado, no
necesariamente las palabras exactas de quien las tomó.

1. **Triaje por valor diferencial, no por urgencia** (v3.0). La pregunta no es
   «¿es urgente?» sino «¿leer esto cambiaría algo que vaya a hacer?». Se eligió
   porque para una sola persona el cuello de botella no es la urgencia sino la
   atención mal gastada. _Alternativa descartada_: un clasificador clásico
   urgente/no-urgente — más simple y estándar, pero ciego al valor de la
   información.

2. **30 criterios epistémicos sobre 5 ejes acotados** (v3.0). Descomponer el
   juicio en dimensiones auditables (valor decisional, calidad epistémica,
   riesgo de manipulación, coste cognitivo, presión de acción) en vez de un
   número opaco. _Alternativa descartada_: un score monolítico — más simple,
   pero no explicable ni corregible criterio a criterio.

3. **El config personal vive fuera del repo** (v3.4). En `~/.email-triage/`,
   para sobrevivir al `git reset --hard` de las actualizaciones y no filtrarse
   a git. _Alternativa descartada_ (la vieja, v3.3): el config dentro del repo
   — se abandonó porque el reset lo borraba. Su cara B aparece arriba en
   «Actualizar cuando cambia la estructura del config».

4. **Lo mecánico, en Python; lo de juicio, en el modelo** (v3.4). El decay de
   correcciones y la sanitización S0–S5 pasaron de aritmética mental a código.
   El motivo de seguridad es clave: la defensa anti-inyección deja de ser una
   *instrucción* al modelo y pasa a ser un *mecanismo* (el modelo solo ve texto
   ya filtrado). _Alternativa descartada_: seguir confiando en que el modelo
   recuerde no obedecer al cuerpo del correo.

5. **Scoring: mental por defecto, determinista bajo petición** (v3.6). El
   reparto elegido es «el modelo juzga cada criterio, el script hace el
   recuento». Por defecto se queda en **mental** para conservar el matiz que
   ninguna tabla captura; el modo **determinista** se activa a voluntad cuando
   quieres reproducibilidad (auditar, comparar pesos). _Alternativas no tomadas
   (de momento)_: (a) determinista total por defecto — máxima reproducibilidad,
   pero quita al modelo la corrección «de bulto»; (b) híbrido ancla+ajuste — el
   script fija un ancla y el modelo la mueve dentro de una banda con
   justificación — más fino, pero más complejo de especificar. El **mapeo de
   cada criterio a un solo eje** es otra decisión revisable: se prefirió un eje
   primario por criterio (razonable y testeable) frente a permitir que un
   criterio sume a varios ejes (más fiel, más difícil de razonar).

6. **S0 ancla patrones a contexto en vez de ampliar la blocklist** (v3.4.1, y
   omisión deliberada en v3.6). Más patrones de ataque dan un retorno marginal
   bajo frente al riesgo de marcar correo legítimo como inyección (falsos
   positivos que rompen el triaje diario). _Alternativa no tomada_: una
   blocklist más agresiva — solo valdría la pena si tu modelo de amenaza
   prioriza ataques dirigidos sobre la fricción cotidiana.

7. **Inyección detectada capa el tier, no solo resta puntos** (v3.5). Un atacante
   controla los metadatos que suman (pregunta +4, deadline +4, mención +3), así
   que restar −3 no bastaba: llegaba a `REPLY_NEEDED` igual. Ahora la inyección
   topa el tier en `REVIEW` y obliga a que un humano lo vea. _Alternativa
   descartada_: quedarse solo con la penalización numérica.

8. **El +5 de «hilo esperando respuesta» se verifica de verdad** (v3.5). La
   señal era invisible (tus envíos viven en Enviados, fuera de la bandeja
   triada), así que se disparaba casi siempre. Se eligió **verificar** contra
   Enviados (iCloud) o leer el hilo nativo (`threadId` en Gmail). _Alternativa
   no tomada_: rebajar el peso a +2 fijo — se prefirió arreglar la señal antes
   que degradarla.

9. **Log de sesión append-only** (v3.5). Editar líneas ya escritas del JSONL
   corrompía justo el archivo que permite revertir; ahora fallos y reversiones
   se anotan como eventos nuevos y el undo solo lee. _Alternativa descartada_:
   mutar el `status` en sitio.

10. **Modo rutina opt-in (`activo: false`)** (v3.4.3). Una plantilla recién
    instalada no debe mover correo de forma desatendida sin consentimiento
    explícito. _Alternativa descartada_: arrancar en `true` por comodidad.

11. **Rescate del config antes del `reset --hard`** (v3.6). Quien venía de v3.3
    con su config dentro del repo lo perdía en silencio al actualizar. Ahora,
    si el config del repo fue editado y aún no hay config externo, se rescata
    antes del reset. _Alternativa descartada_: dejarlo como estaba (un commit
    previo lo daba por hecho sin implementarlo realmente).

12. **REPLY_NEEDED es una señal de acción, no un umbral de importancia** (v3.7).
    Se separó deliberadamente "esto importa mucho" (que ordena REVIEW/READING_LATER
    por score) de "esto exige tu respuesta" (que es REPLY_NEEDED). Solo las
    condiciones de acción explícitas (pregunta directa, deadline, hilo bloqueado)
    suben a REPLY_NEEDED. _Alternativa descartada_: gatear por `presion_accion > 0`
    — se vio en pruebas que `impacto_causal_real` contamina ese eje y dejaba pasar
    newsletters de alto impacto pero sin réplica esperada. _Cara B_: algo
    genuinamente urgente que el modelo no marque con la señal explícita se queda
    en REVIEW; la corrección manual (que alimenta el aprendizaje) es la vía para
    subirlo.

## Créditos
Diseñado por Pablo Rodríguez López ([mindandhealth.org](https://mindandhealth.org/)) con asistencia de Claude.

Criterios epistémicos basados en las [Sequences](https://www.lesswrong.com/rationality) de Eliezer Yudkowsky (LessWrong).

## Licencia
Apache 2.0 — ver [LICENSE](https://github.com/novanoticia/email-triage-plugin/blob/main/LICENSE).

## Enlaces adicionales
- [Repositorio en GitHub](https://github.com/novanoticia/email-triage-plugin)
- [Issues](https://github.com/novanoticia/email-triage-plugin/issues)
- [Releases](https://github.com/novanoticia/email-triage-plugin/releases)


---

> _Nota: parte de la documentación y del código de este repositorio se ha
> elaborado con asistencia de IA (Claude) y requiere revisión humana antes de
> darse por definitiva._
