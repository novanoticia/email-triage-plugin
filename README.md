# Email Triage Plugin v3.3.0

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
- **Defensa prompt injection (3 capas)**: delimitadores `<email-body-data>`, detector S0 sobre el cuerpo sanitizado, framing como *datos no instrucciones*
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
`~/.claude/plugins/marketplaces/email-triage-plugin/` (o `git pull`
para actualizar).

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
Edita `skills/email-triage/config.yaml` antes del primer uso:

### Campos básicos
- `usuario`: nombre, perfil profesional, proyectos activos
- `correo`: proveedor (icloud/gmail/otro), nombre de cuenta
- `carpetas`: bandeja, pendiente, destino, historial

### Modos de interacción
- `confirmacion`: pregunta uno a uno (recomendado al inicio)
- `lote`: presenta todos y pide confirmación global
- `silencioso`: mueve automáticamente (tras validar el criterio)
- `simulacion`: dry-run, no mueve nada (también activable diciendo "simula" / "qué movería")
- **rutina** (v3.3): activado solo cuando el skill se ejecuta desde una scheduled task. Configura el bloque `interaccion.rutina` para definir umbral de movimiento, lista de candidatos dudosos y notificación macOS al terminar.

### Configuración del modo rutina
```yaml
interaccion:
  modo: "confirmacion"           # modo manual habitual
  rutina:
    activo: true                 # respetar este bloque en scheduled tasks
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
Reduce `puntuacion.max_caracteres_cuerpo` a 300 o desactiva `leer_cuerpo` si prefieres velocidad sobre precisión.

## Créditos
Diseñado por Pablo Rodríguez López ([mindandhealth.org](https://mindandhealth.org/)) con asistencia de Claude.

Criterios epistémicos basados en las [Sequences](https://www.lesswrong.com/rationality) de Eliezer Yudkowsky (LessWrong).

## Licencia
Apache 2.0 — ver [LICENSE](https://github.com/novanoticia/email-triage-plugin/blob/main/LICENSE).

## Enlaces adicionales
- [Repositorio en GitHub](https://github.com/novanoticia/email-triage-plugin)
- [Issues](https://github.com/novanoticia/email-triage-plugin/issues)
- [Releases](https://github.com/novanoticia/email-triage-plugin/releases)
