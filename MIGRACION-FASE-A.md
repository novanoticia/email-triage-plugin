# Migración — integrar la Fase A (y qué viene después)

## 1. Qué integrar (aditivo, sin riesgo)

Copia estos ficheros a `plugins/email-triage/skills/email-triage/scripts/`:

- `contracts.py`
- `adapter_mailapp.py`
- `adapter_gmail.py`
- `test_contratos_fase_a.py`

Y `ARCHITECTURE.md` + este fichero donde prefieras (raíz del skill o del repo).

**No se modifica ningún fichero existente.** `triage_helpers.py`, `SKILL.md`,
`config.yaml` y los dos test suites previos quedan intactos. Por eso es
seguro: si algo del contrato no te convence, borras 4 ficheros y no queda
rastro.

## 2. Verificación

Desde `plugins/email-triage/skills/email-triage/`:

```bash
python3 -m pip install pytest pyyaml --break-system-packages
python3 -m pytest scripts/ -q
```

Esperado: **los 267 tests previos + 15 nuevos = 282 passed, 1 xfailed**.
Si los 267 previos siguen verdes, la Fase A no ha tocado el comportamiento.

## 3. CI de versiones

Tu `.github/workflows/tests.yml` ya corre `scripts/`, así que recogerá los
tests nuevos sin cambios. El gate de coherencia de versiones (que sincroniza
`plugin.json`/`marketplace.json`/`SKILL.md`/`config.yaml`) NO se ve afectado:
los ficheros nuevos no llevan número de versión propio. Si en el futuro
quieres versionar el contrato, añade `contracts.py` como 6.º sitio de versión.

## 4. Uso mínimo desde el orquestador (opcional)

Hoy el `SKILL.md` invoca `triage_helpers.py montar-*` por ruta. El adaptador
NO obliga a cambiar eso: es una fachada Python equivalente. Ejemplo:

```python
from adapter_mailapp import MailAppAdapter  # cumple el puerto AdaptadorCorreo
ad = MailAppAdapter(cuenta="iCloud",
                    carpetas={"origen": "INBOX", "review": "Revisar",
                              "archive": "", "reply_needed": "Pendiente"})
correos = ad.leer_bandeja(limite=50, ventana_horas=48)   # [NormalizedEmail]
# ... el núcleo puntúa (triage_helpers scoring) ...
ad.mover({"review": [c.handle for c in a_revisar]})
```

En sandbox/Linux `leer_bandeja`/`mover` levantan `AdaptadorNoDisponible`
(no hay osascript); la CONSTRUCCIÓN de scripts y el PARSEO sí funcionan en
cualquier sitio (por eso son testeables).

## 5. Fase A.2 (opcional) — split físico

Si algún día quieres que el núcleo viva literalmente en `core/` en vez de
dentro de `triage_helpers.py`:

1. Crea `scripts/core/` y mueve ahí las funciones marcadas **núcleo** en el
   mapa de `ARCHITECTURE.md` (`cmd_sanitizar`, `cmd_scoring*`, `cmd_ajustes`,
   `cmd_agrupar_hilos`, `cmd_validar_config`, `cmd_gate_cuerpo`,
   `cmd_calibrar`, más sus helpers privados).
2. Deja `triage_helpers.py` como dispatcher CLI fino que reexporta desde
   `core/` y `adapters/mailapp/` (así `SKILL.md` y los tests no cambian de
   ruta ni de nombres).
3. Corre la suite: si sigue verde, el split fue mecánico y correcto.

Es "mudanza guiada por el mapa", no rediseño. Se deja fuera de Fase A porque
mover 2.700 líneas tiene más riesgo que valor mientras nadie lo necesite.

## 6. Fase B (cuando haya demanda real) — adaptador Gmail

Implementa `GmailAdapter` (hoy stub) contra la API de Gmail:

- `handle` = id de mensaje de Gmail (no message-id RFC).
- `estado_hilo` = por `threadId` nativo; normalmente SIN `fecha_corte`.
- `mover` = aplicar/quitar **labels**, no mover entre buzones.
- OAuth + hosting: es la parte cara, y es la que hace la versión Gmail
  DISTRIBUIBLE como app de ChatGPT (a diferencia de Mail.app, local).

El núcleo se reutiliza sin cambios: ese es el retorno de haber hecho la Fase A.

## 7. Hallazgos del propio refactor (deuda documentada)

- `estado_hilo`/`montar-consulta-enviados` exige `fecha_corte` no vacío: en el
  puerto es opcional (Gmail no lo necesitará), pero el adaptador Mail.app lo
  requiere. Documentado; el test lo fija.
- `leer_cuerpos` en Mail.app vuelca cuerpos a `/tmp/tbody_N` y necesita
  reasociación por handle; el puerto lo define, pero la implementación fina se
  hereda del flujo actual del `SKILL.md` (pendiente de consolidar en A.2).
