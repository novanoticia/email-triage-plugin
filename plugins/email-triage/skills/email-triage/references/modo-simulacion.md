<!-- Extraído de SKILL.md (PASO 4.G) en v3.18.2: bloque condicional que no
toda sesión necesita. El SKILL.md deja un stub con la condición de entrada
y las garantías de seguridad, y apunta aquí. -->

**Modo `simulacion`** (dry-run):
- Ejecuta TODO el pipeline completo (PASO 0.B ajustes aprendidos, PASO 1.C
  detección de hilos, PASO 1.B sanitización, PASO 4 scoring epistémico)
  exactamente igual que una sesión real
- **NO ejecuta ningún `move`** — ni en iCloud ni en Gmail
- **NO escribe en `session_log.jsonl`** — no hay movimientos que registrar
- **NO escribe en los archivos de telemetría** (`scores.jsonl`, etc.) —
  los datos simulados contaminarían el historial real
  (excepción: el desglose de `telemetria.guardar_desglose`, que solo lee
  `diagnostico-ejes` y no alimenta el aprendizaje, sí se escribe)
- **SÍ registra los overrides del usuario** en `correcciones.jsonl` si el
  usuario corrige un tier durante la revisión del dry-run — esas correcciones
  son datos de aprendizaje válidos aunque no haya movimiento real. Cada
  entrada escrita en simulación DEBE llevar el campo `"simulacion": true`:
  el PASO 0.B les aplica peso reducido (×0.5), porque los dry-runs suelen
  hacerse probando pesos o umbrales experimentales y no deben contaminar
  el perfil de producción con peso completo
- Al final presenta el resumen de simulación (ver PASO 5) con un diff claro
  de qué habría movido, a dónde, y con qué score

**Cuándo usar dry-run**:
- Después de cambiar puntos o umbrales en `config.yaml`
- Después de añadir/quitar remitentes de las listas
- Al inicio de uso del plugin para entender su comportamiento sin riesgo
- Para validar que los ajustes aprendidos (PASO 0.B) están funcionando bien
