# Email Triage Plugin v3.2.0

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
### Instalación automatizada (recomendado)

El instalador clona el repo en `~/.claude/plugins/marketplaces/email-triage-plugin/`,
lee la versión desde `plugin.json`, sincroniza la caché de Claude Code y el rpm de
Cowork, y crea `~/.email-triage/` para los logs de sesión y telemetría.

```bash
curl -O https://raw.githubusercontent.com/novanoticia/email-triage-plugin/main/scripts/install-plugin.sh
chmod +x install-plugin.sh
./install-plugin.sh
```

Requiere `git` y `python3` disponibles en `PATH`.

### Actualización
Ejecuta el mismo script: detecta el repo ya clonado y hace `git fetch` + `reset --hard origin/main`.

```bash
./install-plugin.sh
```

> **Nota Cowork**: tras actualizar, desactiva y vuelve a activar el plugin en
> Cowork para forzar la resincronización de versión.

### Instalación manual (solo si no quieres usar el script)
1. **Claude Code**:
   - Abre "Personalizar" → "Explorar Plugin".
   - Busca "Email-triage-plugin" en la sección "Personal".
   - Haz clic en "Gestionar" para activar el plugin.

2. **Cowork**:
   - Abre "Personalizar" → "Explorar Plugin".
   - Busca "Email-triage-plugin" en la sección "Personal".
   - Haz clic en el botón "+" para agregar el plugin.

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
