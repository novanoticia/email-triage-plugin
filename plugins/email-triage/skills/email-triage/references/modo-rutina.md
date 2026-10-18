<!-- Extraído de SKILL.md (PASO 4.G) en v3.18.2: bloque condicional que no
toda sesión necesita. El SKILL.md deja un stub con la condición de entrada
y las garantías de seguridad, y apunta aquí. -->
<!-- v3.21.9: la detección (antes en PASO 0 del SKILL.md) vive también aquí;
el SKILL.md conserva la condición de entrada. -->

### Detección de modo rutina (scheduled task) — NUEVO en v3.3

Al leer la petición del usuario, determinar si la sesión es una ejecución
desde una scheduled task. La señal canónica es la etiqueta `<scheduled-task>`
en el contexto del prompt.

- **Si existe `<scheduled-task>` en el contexto** Y `interaccion.rutina.activo`
  es `true` en `config.yaml`: activar `modo_rutina: true` para toda la
  sesión. El bloque `interaccion.rutina` sobrescribe `interaccion.modo`.
- **Si existe `<scheduled-task>` pero `rutina.activo` es `false`**: usar
  `interaccion.modo` como en cualquier otra ejecución.
- **Si NO existe `<scheduled-task>`**: ignorar el bloque `rutina` completamente.
  Las invocaciones manuales nunca activan modo rutina.
- **Por defecto**: `modo_rutina: false`.

Cuando `modo_rutina: true`:
1. Anunciar al inicio el timestamp y el modo:
   > ⏱️ **Inicio:** HH:MM:SS — modo rutina (silencioso con umbral)
2. Saltar todas las preguntas de confirmación.
3. **Forzar `scoring.modo: determinista`** durante toda la sesión, ignorando
   el default `mental` del config. En rutina no hay humano que revise una
   clasificación irreproducible antes de que se muevan correos: la aritmética
   del score la hace `triage_helpers.py`, no el juicio del modelo. Es la misma
   disciplina de "mecanismo, no confianza" que ya rige el modo veloz.
4. Aplicar la lógica de PASO 4.G — Modo rutina.
5. Al terminar, marcar timestamp de fin y lanzar notificación de macOS
   (ver PASO 5 — sección rutina).

`modo_simulacion` y `modo_rutina` son compatibles: si la rutina se ejecuta
con `modo_simulacion: true` (porque el config lo marca o porque el prompt
lo pide), se hace dry-run notificando los movimientos hipotéticos.

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
