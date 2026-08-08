<!-- Extraído de SKILL.md por CM2 (auditoría 2026-08-07): bloque
condicional o de consulta que no toda sesión necesita. El SKILL.md deja
un stub con la condición de entrada y apunta aquí. -->

## Personalización (ver config.yaml)

### Filtros y keywords (heredados de v2.0)
- `remitentes_prioritarios` — boost de calibración (+3): va en `extra_points`, no es clave de `hard_rules` (ver 4.A.2)
- `remitentes_ignorar` — skip total (-99)
- `palabras_clave_boost` — con peso: `alto` (+3), `medio` (+2), `bajo` (+1)
- `palabras_clave_penalizar` — reducen puntuación (-2)
- `limite_por_sesion` — máximo por ejecución (default: 50)
- `leer_cuerpo` — `true`/`false`, activa lectura del contenido del email
- `modo` — `confirmacion` (default) | `lote` | `silencioso` | `simulacion`
  (`simulacion` activa dry-run permanente desde config; también se puede
  pedir por lenguaje natural en cada sesión sin cambiar el config)

### Tiers y umbrales (nuevo en v3.0)
- `tiers.reply_needed` — umbral mínimo para tier de respuesta (default: 10)
- `tiers.review` — umbral mínimo para revisión (default: 4)
- `tiers.reading_later` — umbral mínimo para lectura futura (default: 0)
- `tiers.archive` — todo lo que quede por debajo (default: -1)

### Criterios epistémicos (nuevo en v3.0)
- Los 30 criterios con sus pesos están definidos en `criterios_epistemicos`
- Se pueden activar/desactivar individualmente con `activo: true/false`
- Los pesos son ajustables por el usuario

### Telemetría (nuevo en v3.0)

Todos los archivos se escriben en `~/.email-triage/` al final de cada sesión
(PASO 5.B). Formato JSONL — una línea por correo, append incremental.

- `telemetria.guardar_vector` → `~/.email-triage/vectors.jsonl` — vector binario de criterios activados por correo
- `telemetria.guardar_score` → `~/.email-triage/scores.jsonl` — score final y desglose por eje
- `telemetria.guardar_explicacion` → `~/.email-triage/explicaciones.jsonl` — razones positivas/negativas y rationale
- `telemetria.guardar_correccion` → `~/.email-triage/correcciones.jsonl` — overrides del usuario (tier asignado vs corregido)
- `telemetria.exportar_mal_clasificados` → `~/.email-triage/mal_clasificados.jsonl` — subconjunto de correcciones donde el modelo se equivocó

Ver PASO 5.B para los esquemas JSON completos de cada archivo.
