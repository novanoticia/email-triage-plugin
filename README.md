# Email Triage Plugin v3.28.6

[![Versión en main](https://img.shields.io/badge/dynamic/json?url=https%3A%2F%2Fraw.githubusercontent.com%2Fnovanoticia%2Femail-triage-plugin%2Fmain%2Fplugins%2Femail-triage%2Fplugin.json&query=%24.version&prefix=v&label=Versi%C3%B3n%20en%20main&color=blue)](https://github.com/novanoticia/email-triage-plugin/blob/main/plugins/email-triage/plugin.json)
[![Última versión publicada](https://img.shields.io/github/v/release/novanoticia/email-triage-plugin?display_name=tag&label=%C3%9Altima%20versi%C3%B3n%20publicada&color=green)](https://github.com/novanoticia/email-triage-plugin/releases/latest)

Un filtro de correo para **Claude Cowork y Claude Code** que no pregunta «¿es
urgente?», sino **«¿leer esto cambiaría algo concreto para mí?»**.

[Privacy](PRIVACY.md) · [Licencia Apache-2.0](LICENSE)

**En esta página:**
[Qué hace](#qué-hace) ·
[Inicio rápido](#inicio-rápido) ·
[Uso diario](#uso-diario) ·
[Requisitos](#requisitos) ·
[Instalación](#instalación) ·
[Configuración](#configuración) ·
[Problemas frecuentes](#problemas-frecuentes) ·
[Language / Langue](#language--langue) ·
[Cómo funciona por dentro](#cómo-funciona-por-dentro) ·
[Privacidad](#privacidad-y-comunicaciones-de-red) ·
[Historial de cambios](#historial-de-cambios)

## Qué hace

Lee tu bandeja de entrada (iCloud mediante Mail.app, o Gmail mediante un
conector), evalúa cada correo con 30 criterios epistémicos y propone uno de
cuatro destinos, siempre con una explicación breve:

| Destino | Qué significa | Qué hace con el correo |
|---|---|---|
| 🔴 `REPLY_NEEDED` | Alguien espera tu respuesta o hay un plazo explícito | Lo deja a la vista (por defecto, en la bandeja de entrada) |
| 🟡 `REVIEW` | Merece que lo leas con atención | Lo mueve a tu carpeta de destino (`carpetas.destino`) |
| 🔵 `READING_LATER` | Interesante, pero puede esperar | Lo deja en tu carpeta de lectura pendiente |
| ⚪ `ARCHIVE` | Leerlo no cambiaría nada: ruido, rutina o manipulación | Lo archiva, sin borrarlo |

Lo que **no** hace:

- **No mueve nada sin tu permiso.** Por defecto te pregunta antes, y el modo
  simulación no toca el buzón. Mover sin preguntar (modo rutina) hay que
  activarlo a propósito.
- **No obedece lo que diga un correo.** El texto se limpia antes de que lo vea
  el modelo y se trata como datos, nunca como instrucciones.
- **No envía tus correos a servidores del proyecto.** Los scripts se ejecutan en
  tu Mac; el análisis lo hace el modelo del cliente que ya usas. Detalle en
  [Privacidad](#privacidad-y-comunicaciones-de-red).

## Inicio rápido

Unos diez minutos en un Mac. Cada paso enlaza a su explicación completa.

1. **Comprueba que tienes Python 3.9+ y git** ([Requisitos](#requisitos)):

   ```bash
   python3 --version && git --version
   ```

2. **Instala PyYAML.** Sin él el plugin clasifica, pero no mueve correos:

   ```bash
   python3 -m pip install --user pyyaml
   ```

3. **Descarga el plugin** con el instalador ([Instalación](#instalación)):

   ```bash
   curl -O https://raw.githubusercontent.com/novanoticia/email-triage-plugin/main/scripts/install-plugin.sh
   chmod +x install-plugin.sh
   ./install-plugin.sh
   ```

4. **Actívalo en la app.** En Claude Code o Cowork: **Personalizar → Explorar
   plugins → sección «Personal» → Email-triage-plugin → «+»**. Sin este paso la
   app no ve el plugin.

5. **Rellena tus datos** en `~/.email-triage/config.yaml` (lo crea el
   instalador). Son obligatorios cuatro campos:
   - `usuario.nombre` — tu nombre.
   - `usuario.perfil` — 2-4 líneas sobre tu trabajo e intereses. Es el ancla del
     triaje: cuanto mejor lo describas, mejores decisiones.
   - `correo.proveedor` — `icloud`, `gmail` u `otro`.
   - `correo.cuenta` — el nombre de la cuenta en Mail.app (p. ej. `iCloud`) o tu
     dirección de Gmail.

   Revisa también que los nombres de `carpetas` coincidan **exactamente** con
   los de tu correo. Más en [Configuración](#configuración).

6. **Haz una prueba sin riesgo.** Escribe `/triage dry-run` o «simula el
   triaje». Verás qué movería y por qué, sin tocar nada.

7. **Cuando te convenza, haz el triaje real** con `/triage`. Te enseña la
   propuesta agrupada por destino y te pide confirmación antes de mover.

## Uso diario

Puedes usar el comando `/triage` (solo en Claude Code) o pedirlo con tus
palabras. Algunas frases que el plugin reconoce:

| Quieres… | Escribe |
|---|---|
| Triar la bandeja de entrada | `/triage` o «haz el triaje del correo» |
| Ver qué haría, sin mover nada | `/triage dry-run`, «simula el triaje» o «qué movería» |
| Revisar una carpeta concreta | `/triage Leer Después` o «revisa Leer Después» |
| Un barrido rápido y barato | «triaje veloz» ([Modo veloz](#modo-veloz)) |
| Deshacer el último triaje | «deshaz el triaje» |
| Corregir una decisión | Dilo en la conversación («este no es ARCHIVE, es REVIEW»); el plugin lo registra y aprende de ello |
| Resultados en inglés o francés | Añade `idioma=en` o `idioma=fr` ([Language / Langue](#language--langue)) |
| Puntuación reproducible y auditable | «modo determinista» |

Al terminar, el plugin muestra un resumen de la sesión: cuántos correos fueron
a cada destino, cuántos dudosos quedan para ti y cómo deshacer.

## Requisitos

- **`git` y `python3`** en el `PATH` (Python 3.9+).
- **PyYAML** — lo usa el subcomando `scoring` (`scripts/triage_helpers.py
  scoring`). Desde v3.21.12 es **necesario para mover correos**: sin él, el
  skill clasifica y propone en **modo mental** (sin romperse), pero no mueve
  nada, porque mover exige la puntuación del script. Instálalo con:

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
Se eligen con `interaccion.modo` en tu config:

- `por_tier` (**por defecto**): una pregunta por destino, en formato compacto y con los correos numerados (#N); los lotes pequeños se confirman uno a uno (`umbral_uno_a_uno`)
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
| Criterios evaluados | 13 *core* | hasta 30 |
| Scoring | determinista + `--brief` | mental |
| Calibración | se omite / reutiliza | cada sesión |
| Verificación contra Enviados | se omite | activa |
| Cuerpo leído | 800 car. | 1500 car. |
| Explicación | 1+1 razones, sin rationale | 3+3 + rationale |

Ahorro típico estimado: **~45–60 % de tokens** por sesión (~50 correos).
Compatible con `simulacion` y `rutina`.

### Alternancia de modelos del mismo proveedor (opcional)

El triaje habitual sigue funcionando sin cambios de configuración. Para probar
la alternancia, pide **«compara modelos nativos en una simulación del triaje»**.
El asistente comprobará las capacidades disponibles y mantendrá el principal si
no puede delegar de forma compatible.

Para conservar la preferencia, copia la plantilla
[`config-modelos.yaml`](plugins/email-triage/skills/email-triage/config-modelos.yaml)
a `~/.email-triage/config-modelos.yaml` (o a la base `EMAIL_TRIAGE_HOME`) y usa:

```yaml
modo: comparar       # actual | comparar | hibrido
modelo: ""           # resolver desde el catálogo real del cliente
max_llamadas: 2
tamano_lote: 25
```

- **`actual`:** comportamiento previo. También es el predeterminado si falta la capa.
- **`comparar`:** simulación sin mover correos. Compara los mismos criterios,
  contexto y scoring determinista entre principal y alternativa. Revisa los
  desacuerdos antes de adoptar el modo híbrido.
- **`hibrido`:** delega criterios en lotes y conserva en el principal el contexto,
  las reglas, la revisión y los movimientos autorizados. Los archivos propuestos,
  los mensajes que requieren respuesta y los casos dudosos se reevalúan.

Puedes fijar `modelo` con un ID que el host realmente admita. Se selecciona Haiku
u otra opción económica del **proveedor actual** según disponibilidad observada;
no hay un ID universal ni se presupone qué versión está habilitada. Si el
principal ya es ese modelo, se continúa directamente sin delegación redundante.

La alternancia nativa no añade APIs ni facturación API propia. Sus llamadas
pueden consumir la cuota o facturación del cliente actual. No se cambian los
controles de privacidad; sí puede existir contexto adicional de subagente dentro
de la misma conexión. La capa externa de Jev es independiente y está desactivada
por defecto: requiere consentimiento y clave propia, añade consumo en TypeSafe
y admite comparación sin movimientos o híbrido explícito con revisión del principal
y las autorizaciones existentes.
[Guía de Jev](plugins/email-triage/skills/email-triage/references/jev.md) (clave
`TYPESAFE_API_KEY`: misma guía del Llavero, [`docs/claves-api-macos.md`](docs/claves-api-macos.md)).
La capa de **OpenAI Decisions** funciona igual (mismo núcleo común, modos y frenos),
también desactivada por defecto, con `OPENAI_API_KEY` propia y facturación aparte
en OpenAI; no se combina con Jev ni con la delegación nativa en la misma sesión.
[Guía de Decisions](plugins/email-triage/skills/email-triage/references/decisions.md) ·
[Cómo guardar las claves de API en el Mac](docs/claves-api-macos.md).

Contrato completo y límites:
[`references/modelos-nativos.md`](plugins/email-triage/skills/email-triage/references/modelos-nativos.md).

### Tiers y umbrales
- `tiers`: umbrales configurables para cada tier
- `hard_rules`: puntos fijos por señales deterministas

## Problemas frecuentes
### «Instalé la nueva versión, pero sigue saliendo la antigua»
Falta el paso 2 de la instalación: en la app, **Personalizar → Explorar plugins → Email-triage-plugin → «Gestionar»**, desactívalo y vuelve a activarlo. Ver [Paso 2](#paso-2--registrar--refrescar-en-la-app-obligatorio).

### Clasifica, pero no mueve ningún correo
Comprueba dos cosas: que no estés en simulación (`dry-run`, «simula», o `interaccion.modo: "simulacion"` en tu config) y que PyYAML esté instalado para el mismo `python3` que usa el plugin (`python3 -c "import yaml"`). Sin PyYAML el plugin clasifica y propone, pero no mueve nada. Ver [Requisitos](#requisitos).

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

## Language / Langue

> Elaborado con asistencia de IA; requiere revisión humana.

**Idiomas disponibles:** español (`es`, por defecto), inglés (`en`) y francés (`fr`).

**Cómo elegir el idioma.** Añade `idioma=en` o `idioma=fr` (también vale `lang=`) a tu
petición, por ejemplo `/triage dry-run idioma=fr`. Un código suelto como `en` o `es` no
cuenta: chocaría con la preposición o el verbo españoles. También puedes fijarlo en tu
config personal (`~/.email-triage/config.yaml`) con `usuario.idioma`; la marca de la
petición manda sobre ese valor. Un mensaje de seguimiento de la misma conversación, sin
`/triage` ni marca, conserva el idioma de la última invocación. Sin nada de eso, el
plugin funciona en español exactamente como siempre. Un código vacío, mal formado o sin catálogo no rompe nada: se
avisa y se continúa en español.

**Qué se traduce y qué no.** Se traduce lo que el skill te muestra (resumen de sesión,
tablas, preguntas de confirmación, errores) y el agente responde en ese idioma. No se
traducen los tiers (`REPLY_NEEDED`, `REVIEW`, `READING_LATER`, `ARCHIVE`), los modos, las
claves JSON, lo que se escribe en disco (JSONL, telemetría) ni las instrucciones
internas del skill.

**Cómo añadir un idioma.** Se suelta un fichero `i18n/<código>.yaml` y se valida con
`python3 scripts/i18n_validar.py`; los pasos están en
[`i18n/README.md`](plugins/email-triage/skills/email-triage/i18n/README.md).

**Estado de las traducciones — léelo antes de fiarte de ellas:**

- Las traducciones `en` y `fr` las ha escrito una IA: **ninguna traducción está
  revisada** por una persona. Las frases que confirman mover, archivar o deshacer
  (`riesgo: alto` en el catálogo) necesitan revisión humana.
- El **texto libre** que el modelo redacta en el momento (resúmenes, razones, notas) sale
  en el idioma elegido y **no está revisado**.
- La detección de inyección de prompts (S0) cubre **español, inglés y francés** y **no cambia
  con `idioma=`**: depende del idioma del correo recibido, no del de la interfaz. Los patrones
  franceses se aplican también con interfaz en español. La detección es heurística;
  un correo hostil en otros idiomas o con patrones nuevos puede evadirla. El escapado
  mecánico y el tratamiento del cuerpo como dato siguen vigentes.
- Los mensajes de error de los scripts siguen en español; el modelo los explica en el
  idioma elegido.
- Sin prueba en plataforma real (Claude Code / Cowork): hasta ahora solo pruebas
  automáticas y simulaciones.

Translation: AI-generated, not reviewed by a human. / Traduction générée par une IA, non
relue par un humain. / Traducción generada por una IA, sin revisión humana.

## Cómo funciona por dentro

### Filosofía

Evalúa correos electrónicos usando un marco de racionalidad bayesiana inspirado en las [LessWrong Sequences](https://www.lesswrong.com/rationality): no "¿es importante?" sino "¿leer esto cambiaría algo concreto para mí?"

Analiza cada correo con 30 criterios epistémicos, genera una puntuación multi-eje (valor decisional, calidad epistémica, riesgo de manipulación, coste cognitivo, presión de acción) y clasifica en 4 tiers con una explicación legible de cada decisión.

La mayoría de clasificadores de correo preguntan "¿es urgente?". Este plugin pregunta algo distinto:
- ¿Cambia una decisión? (Value of Information)
- ¿Actualiza mis predicciones? (Bayesian Surprise)
- ¿La evidencia es genuina o filtrada? (Filtered Evidence)
- ¿Explora o racionaliza? (Forward vs Backward Flow)
- ¿Es urgencia real o teatro? (Urgencia fabricada)
- ¿Está anclado a hechos verificables? (Entangled Truths)

El resultado no es un simple "urgente/no urgente" sino un filtro de: valor decisional, calidad epistémica, coste cognitivo y riesgo de manipulación.

### Compatibilidad con otros clientes (Agent Plugins 1.0.0)

> **Compatible con [Agent Plugins 1.0.0](https://agent-plugins.org/specification)** — el
> formato portátil de empaquetado de la Agentic AI Foundation (OpenAI, Amazon, Microsoft,
> Cursor y Vercel, con Google como *core maintainer*). El paquete lleva el manifiesto
> portable `plugin.json` en la raíz del plugin y el skill en
> `plugins/email-triage/skills/email-triage/SKILL.md`, así que cualquier cliente
> conformante lo descubre. Un gate de CI lo verifica en cada commit.
>
> **Qué necesita el cliente para ejecutarlo.** El skill viaja a cualquier cliente
> conformante, pero para *actuar* sobre el correo el cliente tiene que poder hacer dos
> cosas: **alcanzar el buzón** (Mail.app en macOS, el MCP de Gmail, u otra vía de acceso
> a la cuenta) y **ejecutar los scripts de `scripts/`** — Python 3.9+, solo stdlib, para
> el sanitizado S0–S5 y la aritmética del scoring. Un cliente que cumpla ambas cosas lo
> ejecuta; uno que no, puede leer el skill y razonar con sus criterios, pero no mover
> nada. Está declarado en el campo `compatibility`, que es donde la especificación de
> Agent Skills manda poner los requisitos de entorno.
>
> Deliberadamente no lleva una lista de qué productos pueden y no pueden: las
> capacidades de cada cliente cambian, y una lista así envejece mal. Verificado en
> agosto de 2026: **ChatGPT sí llega al buzón de iCloud y mueve correos** con el skill
> cargado. Si tu cliente puede acceder a tu correo, pruébalo — en seco primero, con
> «simula el triaje», que no mueve nada.

## Decisiones de diseño

Esta sección recoge las decisiones de fondo del plugin: no *qué* hace cada
versión (eso está en el [historial de cambios](CHANGELOG.md)), sino **por qué** se eligió un camino y
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

## Privacidad y comunicaciones de red

Este plugin no envía el contenido de los correos a servidores operados por este proyecto.

- En macOS, trabaja localmente mediante Mail.app y AppleScript.
- Puede utilizar un acceso a Gmail u otro proveedor si el usuario configura un conector en su cliente de IA.
- Los datos locales de configuración, calibración y registro se guardan en el directorio de estado del plugin (`EMAIL_TRIAGE_HOME` o una ubicación equivalente).
- El proyecto no incorpora telemetría, analítica ni servicios remotos propios.

Si en una versión futura se añade un servicio remoto operado por el proyecto, se publicará una política de privacidad antes de habilitarlo.

## Notes for reviewers

These notes explain the automated findings of the Claude plugin directory
scan.

- **Scope.** The repository root also holds development tooling (tests, CI
  workflows, maintainer scripts) that is not part of the installed plugin. The
  distributable plugin lives in [`plugins/email-triage/`](plugins/email-triage/).
- **"Uses a credential from the user's machine".** The plugin itself reads no
  credentials. The finding most likely comes from development tooling: the
  `GH_TOKEN` provided by GitHub Actions in `.github/workflows/release.yml`,
  and/or `fix-cowork-version.sh`, a local maintainer script. The plugin runs
  neither.
- **"Contains a download-and-run command".** The `curl …|bash` strings are
  prompt-injection payloads inside unit tests (`tests/test_triage_helpers.py`).
  The tests check that they are escaped and never executed.
- **"Image or font file that the plugin's code could run".** `icon.png` is
  only the listing icon. No code opens or executes it.
- **Privacy.** See [PRIVACY.md](PRIVACY.md).

## Créditos
Diseñado por Pablo Rodríguez López ([mindandhealth.org](https://mindandhealth.org/)) con asistencia de Claude y ChatGPT, y revisiones automatizadas con modelos de [Mistral AI](https://github.com/mistralai). Consulta [CONTRIBUTORS.md](CONTRIBUTORS.md) para el detalle de las contribuciones.

Criterios epistémicos basados en las [Sequences](https://www.lesswrong.com/rationality) de Eliezer Yudkowsky (LessWrong).

## Licencia
Apache 2.0 — ver [LICENSE](https://github.com/novanoticia/email-triage-plugin/blob/main/LICENSE).

## Enlaces adicionales
- [Repositorio en GitHub](https://github.com/novanoticia/email-triage-plugin)
- [Issues](https://github.com/novanoticia/email-triage-plugin/issues)
- [Releases](https://github.com/novanoticia/email-triage-plugin/releases)

## Historial de cambios

Las novedades de cada versión están en [CHANGELOG.md](CHANGELOG.md), de la más reciente a la más antigua. Para usar el plugin no hace falta leerlo; sí conviene mirar la entrada de la versión que instales, por si pide [actualizar tu config](#actualizar-cuando-cambia-la-estructura-del-config).

---
> _Nota: parte de la documentación y del código de este repositorio se ha
> elaborado con asistencia de IA (Claude) y requiere revisión humana antes de
> darse por definitiva._
