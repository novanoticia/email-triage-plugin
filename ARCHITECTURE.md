# Arquitectura — frontera núcleo ↔ adaptador (Fase A)

> Estado: **Fase A completada de forma aditiva.** El motor
> (`triage_helpers.py`) NO se ha tocado; los 267 tests previos siguen verdes.
> Se ha añadido una capa de contrato encima. El "split físico" (mover las
> funciones agnósticas a un paquete `core/`) es opcional y queda descrito como
> Fase A.2 en `MIGRACION-FASE-A.md`.

## La idea en una frase

Un mismo cerebro de scoring, dos cuerpos de correo. El núcleo nunca sabe de
dónde viene el correo ni cómo se mueve: consume `NormalizedEmail` y decide
tiers. Cada backend (Mail.app hoy, Gmail mañana) traduce SU mundo a ese objeto
y ejecuta los movimientos, cumpliendo el puerto `AdaptadorCorreo`.

```
                     ┌─────────────────────────────┐
   Mail.app  ──┐     │   NÚCLEO (agnóstico)        │
   (AppleScript)│    │   triage_helpers.py:        │
                ├──▶ │   sanitizar · scoring ·     │
   Gmail (API) ─┘    │   ajustes · agrupar-hilos · │
   [Fase B]          │   validar-config · gate ·   │
        ▲            │   calibrar                  │
        │            └─────────────────────────────┘
   AdaptadorCorreo (puerto)          ▲
   produce NormalizedEmail ──────────┘
```

## El objeto de intercambio: `NormalizedEmail`

`contracts.py`. Lleva el correo CRUDO (pre-sanitización); limpiar y puntuar es
trabajo del núcleo. Campos clave:

| Campo | Qué es | Quién lo rellena |
|---|---|---|
| `id` / `handle` | id de lote / asa opaca para leer y mover | adaptador |
| `remitente`, `asunto`, `cuerpo_crudo`, `fecha` | datos crudos | adaptador |
| `clave_hilo` | clave de agrupación de hilo | adaptador |
| `respuesta_pendiente` | tri-estado `True`(+5, pendiente)/`None`(+2)/`False`(0) | adaptador (verifica) |
| `remitente_en_historial` | ¿lo conserva el usuario? (atenúa sender_bulk) | adaptador + config |
| `adapter_private` | passthrough privado del backend (p. ej. labels Gmail) | adaptador; el núcleo NUNCA lo lee |

`respuesta_pendiente` es el mejor ejemplo de la frontera: misma señal
semántica, implementación radicalmente distinta —Mail.app la resuelve mirando
la carpeta Enviados; Gmail, con el `threadId` nativo—. El núcleo solo ve el
tri-estado.

## El puerto: `AdaptadorCorreo`

Cuatro verbos, deliberadamente mínimos (no se añaden métodos "por si acaso" de
otra plataforma):

- `leer_bandeja(origen, limite, ventana_horas) -> [NormalizedEmail]`
- `leer_cuerpos([NormalizedEmail]) -> [NormalizedEmail]`
- `estado_hilo(clave_hilo, fecha_corte) -> True|False|None`
- `mover({tier: [handle, ...]}) -> {"ok": ...}` — solo tiers en `tiers_soportados` del adaptador

Detalles que son **configuración del adaptador, no del puerto**: los nombres de
carpeta destino (Mail.app mueve entre buzones; Gmail aplicaría labels) se fijan
al construir el adaptador, no en la firma de `mover()`.

## Mapa subcomando → capa

El seam ya existía de facto en `triage_helpers.py`: sus subcomandos se parten
limpiamente en las dos capas. Esto es lo que hace barata la Fase A.

| Subcomando actual | Capa | Notas |
|---|---|---|
| `sanitizar` | **núcleo** | S0–S5 sobre cuerpo/asunto/remitente |
| `scoring` | **núcleo** | agregación de veredictos → score/tier |
| `ajustes` | **núcleo** | decay de correcciones |
| `agrupar-hilos` | **núcleo** | union-find por clave_hilo |
| `validar-config` | **núcleo** | |
| `gate-cuerpo` | **núcleo** | |
| `calibrar` | **núcleo** | perfil desde remitentes/asuntos |
| `registrar`, `compactar` | **núcleo (infra)** | JSONL append/housekeeping, agnóstico |
| `montar-leer-metadatos` | **adaptador Mail.app** | construye SCRIPT 1A |
| `montar-leer-cuerpos` | **adaptador Mail.app** | |
| `montar-mover` | **adaptador Mail.app** | exige `destino_review` |
| `montar-consulta-enviados` | **adaptador Mail.app** | `estado_hilo`; `fecha_corte` obligatorio |
| `escapar-applescript` | **adaptador Mail.app** | escape de literales AppleScript |

Todo lo `montar-*` + `escapar-applescript` = el adaptador Mail.app, que hoy
`adapter_mailapp.py` ENVUELVE (no reescribe).

## Revisión adversarial (aplicada)

El contrato pasó una crítica adversarial delegada. Cambios incorporados:
- `respuesta_pendiente` (antes `usuario_ya_respondio`): nombre y signo alineados;
  prohibido evaluarla por truthiness (colapsaría `False` y `None`).
- `tiers_soportados` por adaptador: Mail.app no enruta `reading_later`, así que
  `mover` lo rechaza con error claro en vez de dejarlo en no-op silencioso.
- `estado_hilo` lanza error de dominio si falta `fecha_corte` (no fuga interna).
- `id` (identidad-para-dedup) vs `handle` (asa-para-operar) y granularidad
  mensaje/hilo documentadas.
- `adapter_private` (antes `extra`): el nombre delata cualquier lectura desde el núcleo.
- Invariantes de `fecha` (ISO/UTC) y `cuerpo_crudo` (lo normaliza el núcleo) fijados.

## Ficheros añadidos en Fase A

```
scripts/
  triage_helpers.py            (SIN CAMBIOS — el motor)
  contracts.py                 NormalizedEmail + puerto AdaptadorCorreo
  adapter_mailapp.py           MailAppAdapter: envuelve montar-* + osascript
  adapter_gmail.py             GmailAdapter: stub que cumple la interfaz
  test_contratos_fase_a.py     15 tests del contrato (verdes)
ARCHITECTURE.md                este documento
MIGRACION-FASE-A.md            integración + Fase A.2 (split) + Fase B (Gmail)
```

## Estado: EXPERIMENTAL — fuera de la ruta de ejecución

> ⚠️ **`contracts.py`, `adapter_mailapp.py`, `adapter_gmail.py` y `core.py` son
> EXPERIMENTALES.** Ningún código de producción los importa: el flujo real sigue
> siendo `SKILL.md` → subcomandos de `triage_helpers.py`. Verificable en un
> comando: `grep -rn "from core\|adapter_mailapp\|from contracts" --include=*.py
> .` solo devuelve `test_*`.
>
> Esto es una decisión, no un olvido (ver MIGRACION-FASE-A.md §5). Pero tiene un
> coste que la auditoría 2026-08-07 hizo visible: `MailAppAdapter
> .construir_script_leer_cuerpos` llevaba un default (`prefijo="/tmp/tbody_"`)
> que el núcleo rechaza siempre, y nadie lo notó porque nada lo ejecuta. **Una
> capa que no corre no se verifica sola.**
>
> **Regla mientras dure el estado experimental:** este documento describe la
> arquitectura *objetivo*, no la vigente. Ante una discrepancia entre lo que
> dice aquí y lo que hace `triage_helpers.py`, manda `triage_helpers.py`.
>
> **Condición de salida (CM1, auditoría 2026-08-07):** se promueve a estable
> cuando exista un segundo backend real (Gmail, Fase B) que lo justifique — no
> antes. Completar la Fase A.2 hoy movería ~2.700 líneas detrás de la fachada y
> rompería los 44 tests de contrato doc↔código a cambio de cero funcionalidad
> nueva, con el plugin en uso diario.

## Qué NO hace la Fase A (a propósito)

- No implementa Gmail (stub que levanta `NotImplementedError`).
- No monta servidor MCP ni Apps SDK de ChatGPT (eso es Fase B/C).
- No mueve físicamente las funciones del motor a `core/` (Fase A.2 opcional).
- No cambia ni un veredicto de scoring: comportamiento idéntico.
