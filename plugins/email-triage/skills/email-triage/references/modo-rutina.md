<!-- Extraído de SKILL.md (PASO 4.G) en v3.18.2: bloque condicional que no
toda sesión necesita. El SKILL.md deja un stub con la condición de entrada
y las garantías de seguridad, y apunta aquí. -->

**Modo `rutina`** (NUEVO en v3.3 — activo cuando `modo_rutina: true`):
- El usuario NO está presente. Cero preguntas, cero confirmaciones.
- Sobrescribe `interaccion.modo` con los parámetros de
  `interaccion.rutina` durante esta ejecución.
- **Scoring determinista obligatorio, con degradación segura si falla.** En
  rutina el scoring corre en modo `determinista` (fijado en PASO 0), no
  `mental`. Si el script determinista NO está disponible o falla (PyYAML
  ausente, `config.yaml` ilegible o roto, `triage_helpers.py` no encontrado):
  **NO caer al modo mental para mover correos sin supervisión**. En su lugar,
  **no mover nada** en esta pasada, listar TODO lo evaluado como dudoso en el
  resumen y anotar que la rutina degradó por fallo del scoring. Mover correos
  con una clasificación irreproducible y sin humano delante es justo lo que
  este modo debe evitar: **fail-closed, no fail-open**. (En sesión manual sí
  es aceptable el fallback a mental de PASO 4.B, porque hay un humano revisando.)
- **Mover** (a `carpetas.destino`): correos con `score_final >= rutina.umbral_mover`.
  **Nota de diseño**: en rutina TODO lo movido va a `carpetas.destino`,
  incluidos los correos que en sesión manual irían a
  `carpetas.destino_reply_needed` (por defecto INBOX). Es deliberado: sin
  humano presente, una sola carpeta-bandeja ("Urgentes Claude") concentra
  lo actionable y evita que la rutina reordene el INBOX. Si prefieres
  conservar el routing por tiers también en rutina, sube `umbral_mover`
  por encima de `tiers.reply_needed` y revisa los dudosos a mano.
- **Listar como dudoso** (sin mover): correos con
  `rutina.umbral_dudoso_min <= score_final <= rutina.umbral_dudoso_max`.
  Quedan en su carpeta original, listados en el resumen final para que
  el humano decida cuando abra la conversación.
- **Dejar sin tocar**: el resto (incluido lo que normalmente iría a archive,
  salvo que `rutina.archivar_automaticamente: true`).
- **NO** preguntar nunca. Si surge una duda de implementación, decidir
  autónomamente y dejar nota breve en el resumen.
- Registrar movimientos en `session_log.jsonl` y telemetría como cualquier
  sesión real (a diferencia de `simulacion`).
- Al terminar, ver PASO 5 — sección rutina (notificación macOS + timestamps).
