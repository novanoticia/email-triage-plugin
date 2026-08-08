<!-- Extraído de SKILL.md por CM2 (auditoría 2026-08-07): bloque
condicional o de consulta que no toda sesión necesita. El SKILL.md deja
un stub con la condición de entrada y apunta aquí. -->

### Resumen de sesión en modo simulación

Cuando `modo_simulacion: true`, sustituir el resumen anterior por este formato.
El encabezado y pie deben dejar claro que NADA se ha movido.

```
───────────────────────────────────
🧪 SIMULACIÓN DE TRIAJE — NADA HA SIDO MOVIDO
───────────────────────────────────
📥 Bandeja de entrada: X correos analizados (sin cambios)
   → Y habrían requerido atención inmediata

📂 [Carpeta pendiente]: X correos analizados (sin cambios)

   Lo que HABRÍA ocurrido:
   🔴 REPLY_NEEDED: N correos → habrían ido a [destino]
   🟡 REVIEW:       N correos → habrían ido a [destino]
   🔵 READING_LATER: N correos → habrían quedado en [pendiente]
   ⚪ ARCHIVE:       N correos → habrían sido archivados

📊 Scoring simulado:
   Puntuación media: X.X | Máxima: X | Mínima: X
   Ejes dominantes: [eje con más peso]

📈 Criterios más activados en la simulación:
   ▲ [criterio positivo más frecuente]: N veces
   ▼ [criterio negativo más frecuente]: N veces

🔄 Correcciones del usuario durante la revisión: N
   [Estas correcciones SÍ se han guardado como datos de aprendizaje]

🧠 Ajustes aprendidos que se habrían aplicado:
   [igual que en sesión real, si los hay]

💡 Para ejecutar este triaje en real: di "ejecuta el triaje" o
   cambia `modo` en config.yaml a `confirmacion`, `lote` o `silencioso`
───────────────────────────────────
🧪 FIN DE SIMULACIÓN — tu bandeja no ha cambiado
───────────────────────────────────
```

### Resumen de sesión en modo rutina (NUEVO en v3.3)

Cuando `modo_rutina: true`, sustituir el resumen anterior por este formato.
La diferencia clave respecto al modo `silencioso` normal: aparece un bloque
explícito de **CANDIDATOS DUDOSOS** que el humano revisará después, y se
marcan timestamps de inicio/fin con duración total.

```
⏱️ Inicio: HH:MM:SS — modo rutina
⏱️ Fin:    HH:MM:SS — duración: M min S s

───────────────────────────────────
RUTINA DE TRIAJE — [fecha YYYY-MM-DD]
───────────────────────────────────
📥 Bandeja de entrada: X correos analizados
📂 [Carpeta pendiente]: X correos analizados

✅ MOVIDOS automáticamente a [destino] (score ≥ umbral_mover):
   N. [Asunto] — [Remitente] — score X — [razón breve, 1 línea]
   ...
   Total: N

🟡 CANDIDATOS DUDOSOS (sin mover, requieren tu decisión):
   N. [Asunto] — [Remitente] — score X — recomendación tentativa: MOVER/DEJAR
   ...
   Total: M

⚪ DEJADOS sin tocar: T correos
   Desglose por motivo:
   - Newsletter genérica: N
   - Información recuperable: N
   - Sin acción ni info útil: N
   - Otros: N

📝 Decisiones autónomas tomadas (si las hubo):
   - [nota breve sobre cualquier ambigüedad resuelta sin preguntar]
───────────────────────────────────
```

Tras imprimir el resumen, lanzar la notificación de macOS si
`rutina.notificacion_macos: true`. Usar `osascript` vía el conector
"Control your Mac":

```applescript
display notification "Triaje: N movidos, M dudosos en T min" ¬
    with title "Email-Triage" ¬
    sound name "Glass"
```

(Sustituir `Glass` por el valor de `rutina.sonido_notificacion`.)

Si la notificación falla (permisos, conector no disponible), continuar
sin error — el resumen ya está impreso en la conversación.

---
