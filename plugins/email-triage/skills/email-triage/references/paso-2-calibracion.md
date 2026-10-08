<!-- Extraído de SKILL.md por CM2 (auditoría 2026-08-07): bloque
condicional o de consulta que no toda sesión necesita. El SKILL.md deja
un stub con la condición de entrada y apunta aquí. -->

## PASO 2 — CALIBRACIÓN ESTADÍSTICA

La calibración extrae patrones reales del historial del usuario. No es una
descripción conceptual: es un análisis cuantitativo que produce datos usables.

### Procedimiento concreto

1. Accede a `carpetas.historial` (por defecto "Conservar").

2. Lee los últimos 100 correos con asunto, remitente y fecha.

3. **Extrae las métricas exactas CON EL SCRIPT** (CM2/F11): la aritmética
   de conteos ya no se hace mentalmente — mismo lote, mismo perfil,
   reproducible. Pasa los metadatos recopilados a `calibrar`:

   ```bash
   # calibrar.json:
   #   {"correos": [
   #   {"remitente": "Ana López <ana@substack.com>", "asunto": "Update semanal"},
   #   {"remitente": "luis@gmail.com", "asunto": "Re: presupuesto"}
   #   ]}
   python3 "<ruta-del-skill>/scripts/triage_helpers.py" calibrar --guardar < ~/.email-triage/tmp/calibrar.json
   ```

   Devuelve el perfil determinista y, con `--guardar`, lo cachea además
   como snapshot atómico en `~/.email-triage/calibracion.json` (esquema 1;
   es lo que el modo veloz reutiliza vía `calibrar --leer`):

   **a) `top_remitentes`** — top 10, con `conteo` y `porcentaje` sobre
   `n_correos`;

   **b) `top_dominios`** — top 5, formato `@dominio.com`;

   **c) `top_keywords`** — top 15 de los asuntos: minúsculas, tokens de ≥3
   caracteres, sin stopwords ES/EN (la MISMA tokenización que los ajustes
   del PASO 0.B: un solo espacio de keywords).

   Dos observaciones siguen siendo TU juicio — el script no las calcula y
   no requieren conteo exacto:

   **d) Distribución temporal**: rango de fechas y pico de conservación
   (mañana/tarde/noche), a ojo sobre los metadatos ya leídos.

   **e) Tipos detectados**: proporción aproximada de newsletters /
   comunicaciones directas / notificaciones de servicio / otros.

4. **Almacena el perfil** como contexto interno para las fases siguientes.
   Úsalo para:
   - Dar +2 puntos a remitentes que aparecen 5+ veces en historial
   - Dar +1 punto a dominios frecuentes
   - Dar +1 punto a correos cuyo asunto contiene keywords del top 15

5. Si `mostrar_calibracion: true`, presenta las métricas al usuario.
   Si no, solo confirma: "Calibración lista: X correos analizados, Y remitentes
   frecuentes, Z keywords identificadas."

### Cuándo recalibrar

- A petición del usuario
- Si más de 3 "No" consecutivos en modo confirmación
- Si la carpeta de historial ha cambiado significativamente (>50 correos nuevos)
- En modo veloz decide el script: `triage_helpers.py calibrar --leer` responde
  `vigente: false` cuando la caché supera el TTL (`--ttl-dias`, por defecto 7)
  o es ilegible — entonces recalibra y regenera con `calibrar --guardar`

### Calidad de la calibración

Si la carpeta tiene contenido muy heterogéneo, informa y sugiere acotar
por rango de fechas o excluir ciertos dominios del análisis.

---
