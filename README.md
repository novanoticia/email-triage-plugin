# Email Triage Plugin v3.6.0

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
- **Defensa prompt injection (3 capas)**: delimitadores `<email-body-data>`, detector S0 sobre el cuerpo sanitizado, framing como *datos no instrucciones* (ampliado en v3.4.1 con doble vista crudo/decodificado y en v3.5 al asunto)
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
