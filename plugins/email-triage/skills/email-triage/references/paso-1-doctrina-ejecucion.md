# Doctrina de ejecución contra Mail.app (bloque para `references/paso-1-proveedores.md`)

> Pegar bajo la sección "iCloud / Mail.app (macOS)", antes de "Vía preferente".
> Extraído de una ejecución real (modo veloz, 50 correos, 2026-07-21) donde
> Mail tardó >6 min y se acumularon procesos osascript zombis compitiendo por
> Mail. Estas reglas convierten la lectura de frágil a predecible.

## Regla 0 — osascript contra Mail NUNCA es síncrono fiable

Cada `osascript` que toca Mail puede tardar **60-180 s** (más si Mail sincroniza).
El conector puede expirar (timeout ~60 s) **mientras el script sigue corriendo en
segundo plano**. Un script que devuelve su resultado solo al final (p. ej. el
SCRIPT 1 v1, que emite metadatos tras volcar los 50 cuerpos) pierde TODA la
salida en un timeout aunque el trabajo ya esté hecho en disco.

**Nunca ejecutes un read de Mail esperando la salida directa del conector.**
Usa siempre el patrón background + espera por condición:

```bash
# 1. lanzar en segundo plano, redirigiendo a fichero
cd ~/.email-triage/tmp && nohup osascript read_meta.scpt > out_meta.txt 2>&1 &

# 2. esperar al marcador de fin con un bucle acotado (< 50 s por llamada)
#    (metadatos: la primera línea "TOTAL:"; cuerpos: "bodies_ok:")
t=0; until grep -q '^TOTAL:' out_meta.txt 2>/dev/null || [ $t -ge 45 ]; do sleep 3; t=$((t+3)); done; head -1 out_meta.txt
# si aún no está, repite SOLO el paso 2
```

**Nunca encadenes `sleep N; cat …` para esperar** (v3.21.6, prueba real
2026-10-18): Claude Code bloquea ese patrón y la lectura se queda a medias. Si
el host ofrece ejecución en segundo plano con aviso de fin (en Claude Code,
`run_in_background` o `Monitor`), úsala para el paso 1 y espera el aviso; si
no, el bucle `until` de arriba, que termina en cuanto aparece el marcador y
nunca pasa de ~45 s por llamada (el conector expira hacia los 60 s).

## Regla 1 — Matar zombis ANTES de relanzar

Un osascript que expiró por timeout **sigue vivo**. Si relanzas, dos o tres
instancias golpean Mail a la vez, se ralentizan entre sí y pueden dejar los
`tbody_*.txt` en estado inconsistente. Antes de cada relanzamiento de una lectura:

```bash
pkill -f read_meta.scpt; pkill -f read_bodies.scpt
t=0; until ! pgrep -f 'read_(meta|bodies).scpt' >/dev/null || [ $t -ge 15 ]; do sleep 1; t=$((t+1)); done
pgrep -f read_bodies.scpt | wc -l   # debe ser 0 antes de seguir
```

Diagnóstico de "va lentísimo": `pgrep -f <script>.scpt | wc -l`. Si es > 1,
tienes zombis compitiendo — mata y relanza uno solo.

## Regla 2 — Metadatos primero, cuerpos después (y en sublotes)

Orden canónico (ver `mail-consolidado-v2.applescript`):

1. **SCRIPT 1A (metadatos)**: sin `content of m`, retorna en segundos. Da el
   índice estable (idx, fecha, remitente, asunto, message-id).
2. **SCRIPT 1B (cuerpos por message-id)**: el orquestador construye la lista de
   mids desde 1A y la pasa en **sublotes de `resiliencia.sublote_con_cuerpo`
   (15)**, no 50 de golpe. El fichero `tbody_i.txt` se indexa por posición EN LA
   LISTA, y el correo se localiza por `whose message id is` → inmune a que entre
   correo nuevo entre 1A y 1B.

⚠️ El SCRIPT 1 v1 hardcodeaba `if n > 50` e **ignoraba
`resiliencia.sublote_con_cuerpo`**. Contradicción interna del propio config.
1B respeta el sublote.

## Regla 3 — Checkpoint del lado orquestador (reanudable)

Antes de pedir un sublote de cuerpos, filtra los mids cuyo `tbody_i.txt` ya
existe y no está vacío. Si una pasada anterior murió a mitad, la siguiente solo
pide lo que falta — no se re-lee todo. (Se hace en Python, no en AppleScript,
para no pagar un `do shell script` de comprobación por correo.)

```python
pendientes = [(i, mid) for i, mid in enumerate(mids, 1)
              if not os.path.getsize_ok(f"tbody_{i}.txt")]  # existe y >0 bytes
```

## Regla 4 — Aviso de primera ejecución en modo veloz

En veloz se anuncia "salta calibración, reutiliza caché". Pero si NO hay caché
(`calibrar --leer` devuelve `vigente:false`), corre igualmente la lectura lenta
del historial. **El primer veloz nunca es veloz.** Avísalo:

> ⏳ Primera ejecución: no hay calibración cacheada, la genero ahora (una lectura
> extra del historial). Las siguientes sesiones veloces reutilizarán la caché.
