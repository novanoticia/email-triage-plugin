<!-- Referencia del modo veloz. El SKILL.md deja un stub con la condición de
entrada y apunta aquí (divulgación progresiva, como PASO 1.C y PASO 5.B). -->

## Detección de modo veloz (opt-in, NUEVO en v3.8)

Perfil de bajo consumo de tokens y menor latencia, a costa de matiz.
Es un **pre-filtro de ruido**, no el evaluador a fondo de 30 criterios.
Para revisión semanal cuidadosa, usar el config normal.

**Activación** (cualquiera de las dos vías):
- Por petición: el usuario dice "triaje veloz", "modo veloz", "rápido y
  barato" o equivalente → activar `modo_veloz: true` para la sesión.
- Por config: `scoring.perfil: veloz` en `~/.email-triage/config.yaml`.

**Carga de la capa de overrides.** Al activarse, ADEMÁS del config normal
(`~/.email-triage/config.yaml`, del que se toman perfil, cuenta, carpetas,
filtros y keywords), cargar la capa `~/.email-triage/config-veloz.yaml`
si existe (o `config-veloz.yaml` junto a este SKILL.md como plantilla) y
superponer SUS valores sobre el config normal SOLO durante esta sesión.
La capa nunca aporta datos personales; solo parámetros de velocidad.

Cuando `modo_veloz: true`, anunciarlo al inicio y aplicar:

1. **Solo criterios core**: evaluar únicamente los 13 criterios con
   `core: true`; omitir los 17 condicionales (no pasarlos al script en
   modo determinista).
2. **Scoring determinista + lote `--brief`**: usar `scoring.modo:
   determinista` e invocar `triage_helpers.py scoring --brief` en lote.
   Pasa la capa veloz al script con `scoring --config-veloz <ruta a
   config-veloz.yaml>`: el script fusiona sus overrides de `scoring` sobre tu
   config por mecanismo (CM2/F7) — no ensambles un config combinado a mano.
   El desglose completo va a fichero añadiendo `--desglose <ruta>` a esa
   misma invocación (CM2/F12), nunca al contexto.
3. **Saltar calibración (PASO 2)**: preguntar primero a la caché con
   `triage_helpers.py calibrar --leer` (la vigencia — TTL 7 días,
   `--ttl-dias` para otro — la decide el script, no tú). Si responde
   `vigente: true`, usar su `perfil` tal cual; si `vigente: false` (no
   existe, corrupta o caducada), correr el PASO 2 una vez terminando en
   `calibrar --guardar` para regenerarla.
4. **Saltar la consulta a Enviados (subpaso de verificación de 1.C)**: marcar
   `usuario_es_ultimo_en_responder: desconocido` (+2, no +5). Ahorra
   round-trips a osascript. El resto del PASO 1.C (agrupación por hilos y
   sus hard rules) se mantiene.
5. **Cuerpo recortado**: `max_caracteres_cuerpo: 800`, `max_lineas_cuerpo: 20`.
6. **Explicación mínima**: 1 razón positiva + 1 negativa, sin rationale.
7. **Presentación compacta**: tabla de 1 línea por correo (asunto ·
   banderita+tier · score), agrupada por tier. Sin bloque extenso por correo.

`modo_veloz` es compatible con `modo_simulacion` y `modo_rutina`. Ahorro
típico estimado: ~45–60 % de tokens frente al perfil por defecto (sesión
de ~50 correos).
