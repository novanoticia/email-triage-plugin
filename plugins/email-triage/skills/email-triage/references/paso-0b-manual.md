# Especificación manual del PASO 0.B (ajustes aprendidos)

> Extraído del SKILL.md en v3.4 para reducir su tamaño en contexto.
> Leer bajo demanda con Desktop Commander.

### 1. Leer y filtrar correcciones

Leer todas las entradas de `correcciones.jsonl`. Aplicar decay temporal:
- Correcciones de los últimos 30 días → peso completo (×1.0)
- Entre 31 y 90 días → peso reducido (×0.5)
- Más de 90 días → ignorar

Cada entrada tiene este formato:
```json
{"session_id":"...","ts":"ISO8601","message_id":"<id>","subject":"...","from":"remitente@dominio.com","tier_asignado":"ARCHIVE","tier_corregido":"REVIEW","score_final":-2}
```

### 2. Calcular dirección de cada corrección

Mapear `tier_asignado` → `tier_corregido` a una dirección numérica:

| Corrección | Dirección |
|------------|-----------|
| ARCHIVE → READING_LATER | +1 |
| ARCHIVE → REVIEW | +2 |
| ARCHIVE → REPLY_NEEDED | +3 |
| READING_LATER → REVIEW | +1 |
| READING_LATER → REPLY_NEEDED | +2 |
| REVIEW → REPLY_NEEDED | +1 |
| REPLY_NEEDED → REVIEW | -1 |
| REVIEW → READING_LATER | -1 |
| REVIEW → ARCHIVE | -2 |
| READING_LATER → ARCHIVE | -1 |
| REPLY_NEEDED → READING_LATER | -2 |
| REPLY_NEEDED → ARCHIVE | -3 |

### 3. Construir tabla de ajustes dinámicos

Agrupar las correcciones (con decay aplicado) por tres dimensiones:

**a) Por remitente** (`from` exacto):
- Sumar direcciones ponderadas de todas sus correcciones
- Si suma ≥ +3 → `ajuste_remitente: +2`
- Si suma ≥ +5 → `ajuste_remitente: +3`
- Si suma ≤ -3 → `ajuste_remitente: -2`
- Si suma ≤ -5 → `ajuste_remitente: -3`
- Entre -2 y +2 → sin ajuste (ruido estadístico)

**b) Por dominio** (parte `@dominio.com` del `from`):
- Misma lógica, umbrales el doble de estrictos (necesita ≥ 6 / ≤ -6 para ajustar)
- Ajuste máximo: ±1

**c) Por keywords en asunto**:
- Extraer palabras del `subject` de cada corrección (excluyendo stopwords)
- Si una keyword aparece en ≥ 3 correcciones UP con peso total ≥ +3 → `ajuste_keyword: +1`
- Si una keyword aparece en ≥ 3 correcciones DOWN con peso total ≤ -3 → `ajuste_keyword: -1`

### 4. Detectar deriva de umbrales

Si en las últimas 20 correcciones (con decay), más del 70% van en la misma
dirección, el modelo tiene un sesgo sistemático. Alertar al usuario:

> "⚠️ Ajuste sugerido: el 75% de tus últimas correcciones suben el tier
> asignado. Considera bajar el umbral de `review` de 4 a 3 en config.yaml
> para que el modelo sea menos conservador."

No aplicar el cambio automáticamente — solo sugerirlo.

### 5. Mostrar resumen de ajustes cargados

Si `mostrar_calibracion: true` en config, mostrar la tabla completa.
Si no, confirmar brevemente:

> "Ajustes aprendidos: N remitentes con boost/penalización, M keywords
> ajustadas, basados en X correcciones de los últimos 90 días."

Si no hay ajustes: no mostrar nada (no hay nada que reportar).

---
