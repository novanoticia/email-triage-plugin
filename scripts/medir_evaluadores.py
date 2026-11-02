#!/usr/bin/env python3
"""Mide por qué las filas de `hibrido` vuelven al principal (evaluadores LLM).

Herramienta de desarrollo (no se distribuye con el plugin). Envía 120 correos
INVENTADOS (nunca reales) al proveedor elegido en modo `hibrido`, con el
config plantilla del repo, y cuenta los motivos por fila, los criterios en
`__no_aplica__` y los tiers de las propuestas. Por correo muestra solo lo que
con correos inventados no expone nada: las dudas, los criterios con evidencia
vacía y, si el eco falla, el eco esperado frente al recibido.

No toca ~/.email-triage, no lee el buzón, no mueve nada y no muestra la
clave. Uso, desde la raíz del repositorio (resultados en
docs/mediciones-evaluadores.md):

    PROVEEDOR=gemini python3 scripts/medir_evaluadores.py
    PROVEEDOR=apple PAUSA=0 python3 scripts/medir_evaluadores.py  # con fm serve
    PROVEEDOR=ollama PAUSA=0 python3 scripts/medir_evaluadores.py  # ~150 min
    N=40 PROVEEDOR=gemini python3 scripts/medir_evaluadores.py      # solo los 40 primeros

PAUSA (segundos entre llamadas, 4.5 por defecto) evita el límite por minuto
del nivel gratuito de Gemini.

Desde la medición 13 cada correo lleva los controles que pondría el principal
(`ESPERADOS` en correos_ficticios.py) y el script compara el tier propuesto
con el esperado. Los aciertos se cuentan aparte en los correos sin F: con F
el tier es `REPLY_NEEDED` lo diga quien lo diga, y ahí no se mide al
evaluador. CONTROLES=vacios reproduce las mediciones 1-12.

Desde la medición 15 cada propuesta muestra su score y sus ejes, y si el tier
falla, a cuántos puntos queda del rango del esperado (rangos de `tiers` en el
config): así se distingue un umbral mal puesto (a 1-2 puntos) de unos
veredictos que no encajan (muy lejos).

Desde la medición 18 hay 80 correos: los 40 de siempre y 40 más largos,
cargados hacia los casos dudosos. N=40 repite solo los primeros, para
comparar con las mediciones 1-17, y los aciertos salen también por bloque.
Desde la medición 20 son 120 (tres bloques de 40); N=80 repite la 18 y la 19.

Desde la medición 21, IDS elige correos sueltos (sin renumerar) y REPETIR los
mide varias veces seguidas, con un resumen por correo de los tiers que salen:
una sola ejecución no basta para saber si un arreglo funciona cuando el mismo
correo cambia de tier de una vez a otra (el 5 sacó 0 en la 18 y la 19, y 27 en
la 20, sin tocar nada).

    IDS=5,49,81-84 REPETIR=5 PROVEEDOR=gemini python3 scripts/medir_evaluadores.py

Desde la medición 25, GUARDAR=RUTA escribe en RUTA (JSON) los veredictos y
controles de cada correo con propuesta, de todas las repeticiones, sin texto
de ningún correo. `scripts/simular_scoring.py RUTA` los vuelve a puntuar con
otros pesos, ejes o rangos sin llamar al proveedor.

    GUARDAR=/tmp/veredictos.json PROVEEDOR=gemini python3 scripts/medir_evaluadores.py

Desde la medición 16 los fallos de tier muestran también los criterios que
puntúan distinto de 0, agrupados por eje: el eje dice dónde se hunde el
correo; el criterio, qué veredicto lo hunde.
"""
import collections
import copy
import os
import re
import sys

PROVEEDOR = os.environ.get("PROVEEDOR", "gemini")

sys.path.insert(0, "plugins/email-triage/skills/email-triage/scripts")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # correos_ficticios
import yaml  # noqa: E402
import evaluadores as ev  # noqa: E402
import triage_helpers as th  # noqa: E402

from correos_ficticios import CORREOS, ESPERADOS, PERFIL, control  # noqa: E402

N = int(os.environ.get("N", str(len(CORREOS))))
CORREOS = CORREOS[:N]  # los ids siguen siendo 1..N: ESPERADOS se indexa igual


def _ids(texto):
    """«5,49,81-84» -> {5, 49, 81, 82, 83, 84}. Vacío: todos. Un trozo que no
    es número o rango creciente lanza ValueError: una selección mal escrita
    nunca debe acabar enviando el banco entero (revisión de Codex, PR #187)."""
    ids = set()
    for parte in filter(None, (x.strip() for x in texto.split(","))):
        desde, _, hasta = parte.partition("-")
        desde, hasta = int(desde), int(hasta or desde)
        if desde < 1 or hasta < desde:
            raise ValueError("rango no válido: %r" % parte)
        ids.update(range(desde, hasta + 1))
    return ids


try:
    IDS = _ids(os.environ.get("IDS", ""))
except ValueError as e:
    sys.exit("IDS no válido (%s); ejemplo: IDS=5,49,81-84" % e)
REPETIR = max(1, int(os.environ.get("REPETIR", "1")))
# (id, asunto, remitente, cuerpo): los ids son los del banco, aunque se elijan sueltos.
SELECCION = [(i + 1, a, rm, c) for i, (a, rm, c) in enumerate(CORREOS) if not IDS or i + 1 in IDS]
if os.environ.get("IDS", "").strip() and not SELECCION:
    sys.exit("IDS no selecciona ningún correo del banco (1-%d)." % len(CORREOS))

VACIOS = os.environ.get("CONTROLES", "") == "vacios"
GUARDAR = os.environ.get("GUARDAR", "").strip()
if GUARDAR and VACIOS:
    sys.exit("GUARDAR no admite CONTROLES=vacios: el simulador compara con ESPERADOS.")
if GUARDAR and not os.path.isdir(os.path.dirname(os.path.abspath(GUARDAR))):
    sys.exit("GUARDAR: no existe la carpeta de %s" % GUARDAR)  # antes de gastar llamadas

cfg = yaml.safe_load(open("plugins/email-triage/skills/email-triage/config.yaml", encoding="utf-8"))
# El núcleo admite como mucho `MAX_LOTE` (50) correos por invocación y por
# `max_llamadas`: es un freno del plugin, no se toca. Se mide en lotes de 40
# (los bloques de ESPERADOS) y se juntan los resultados.
LOTE = 40
lotes = []
for desde in range(0, len(SELECCION), LOTE):
    pl = ev.preparar({"perfil_minimo": PERFIL, "emails": [
        {"id": str(i), "asunto": a, "remitente": rm, "cuerpo": c}
        for i, a, rm, c in SELECCION[desde:desde + LOTE]]})
    for e in pl["emails"]:
        e["control"] = control("" if VACIOS else ESPERADOS[int(e["id"]) - 1][1])
        e["contexto_suficiente"] = True
    lotes.append(pl)
p = {"emails": [e for pl in lotes for e in pl["emails"]]}  # para el detalle del eco

capa = {"activo": True, "acepta_envio_datos": True, "modo": "hibrido",
        "proveedor": PROVEEDOR, "max_llamadas": min(LOTE, len(SELECCION)),
        # Ollama tarda unos 110 s por correo en un Mac de 16 GB (tope 600).
        "timeout_segundos": int(os.environ.get("TIMEOUT", "300" if PROVEEDOR == "ollama" else "60"))}
prov = ev.proveedor(PROVEEDOR)
crudas = {}  # id -> respuesta estructurada tal como llegó (antes de validarla)
medidas = {}  # id -> (tokens de salida, segundos)


def id_enviado(body):
    """Id del correo en el mensaje de usuario, sea cual sea el formato del proveedor."""
    pendientes = [body]
    while pendientes:
        x = pendientes.pop()
        if isinstance(x, dict):
            pendientes.extend(x.values())
        elif isinstance(x, list):
            pendientes.extend(x)
        elif isinstance(x, str):
            m = re.search(r'"id": "(\d+)"', x)
            if m:
                return m.group(1)
    return None


import time  # noqa: E402
PAUSA = float(os.environ.get("PAUSA", "4.5"))  # nivel gratuito: ~15 llamadas/minuto


def capturar(body, key, timeout):
    if crudas or capturar.llamadas:
        time.sleep(PAUSA)
    capturar.llamadas += 1
    t0 = time.monotonic()
    respuesta = prov.solicitar(body, key, timeout)
    segundos = round(time.monotonic() - t0)
    ident = id_enviado(body)
    try:
        salida = prov.uso(respuesta)[1]
    except Exception:
        salida = None
    if ident is not None:
        medidas[str(ident)] = (salida, segundos)
    try:
        contenido = prov.extraer(respuesta)
        for fila in contenido.get("evaluaciones", []):
            crudas[str(fila.get("id"))] = fila
    except Exception:
        pass  # la validación real la hace evaluadores.py
    return respuesta


capturar.llamadas = 0
print("Enviando %d correos inventados a %s%s (unos %d s)..." % (
    len(SELECCION), PROVEEDOR, "" if REPETIR == 1 else ", %d veces" % REPETIR,
    int(len(SELECCION) * REPETIR * PAUSA)))
# Cada repetición evalúa una copia de los lotes: `evaluar` no debe ver el
# estado que dejó la anterior. El informe completo es el de la última.
# `crudas` y `medidas` se vacían al empezar cada una: si no, una respuesta
# rechazada en la última dejaría a la vista dudas, exclusiones y ecos de otra
# pasada (revisión de Codex, PR #187).
repeticiones = []
for _ in range(REPETIR):
    crudas.clear()
    medidas.clear()
    repeticiones.append([ev.evaluar(copy.deepcopy(pl), cfg, capa, capturar) for pl in lotes])
parciales = repeticiones[-1]
if GUARDAR:
    import simular_scoring  # noqa: E402
    print("veredictos guardados en %s: %d filas" % (
        GUARDAR, simular_scoring.guardar(GUARDAR, PROVEEDOR, repeticiones, ESPERADOS)))


def _sumar(valores):
    """Suma de importes; None si alguno falta (coste desconocido)."""
    return None if any(v is None for v in valores) else round(sum(valores), 7)


r = {"ok": all(x.get("ok") for x in parciales),
     "motivo": next((x["motivo"] for x in parciales if x.get("motivo")), "-"),
     "llamadas": sum(x.get("llamadas") or 0 for x in parciales),
     "consumo": {"coste_estimado_usd": _sumar([(x.get("consumo") or {}).get("coste_estimado_usd")
                                               for x in parciales])},
     "cobertura": dict(sum((collections.Counter({k: v for k, v in (x.get("cobertura") or {}).items()
                                                 if isinstance(v, int)}) for x in parciales),
                           collections.Counter())),
     "resultados": [f for x in parciales for f in x["resultados"]]}

motivos = collections.Counter(f.get("motivo") for f in r["resultados"])
no_aplica = collections.Counter()
con_dudas = 0
tiers = collections.Counter()
for f in r["resultados"]:
    # Desde la respuesta capturada ANTES de validarla: `evaluacion_<proveedor>`
    # solo existe si la fila pasa el eco y la validación, y contar desde ahí
    # ocultaría las dudas y exclusiones de las filas rechazadas.
    crit = (crudas.get(f["id"]) or {}).get("criterios") or {}
    no_aplica.update(k for k, c in crit.items()
                     if isinstance(c, dict) and c.get("veredicto") == "__no_aplica__")
    con_dudas += bool((crudas.get(f["id"]) or {}).get("dudas"))
    if f.get("propuesta"):
        tiers[f["propuesta"]["tier"]] += 1

print("proveedor:", PROVEEDOR, "| ok:", r.get("ok"), "| motivo general:", r.get("motivo", "-"),
      "| llamadas:", r.get("llamadas"), "| coste USD:", r["consumo"].get("coste_estimado_usd"))
print("cobertura:", r.get("cobertura"))
print("motivos por fila:")
for m, n in motivos.most_common():
    print("   %-36s %d" % (m, n))
print("filas con dudas anotadas (también las rechazadas):", con_dudas, "de", len(SELECCION))
print("propuestas (validadas + a reevaluar):", sum("propuesta" in f for f in r["resultados"]), "de", len(SELECCION))
print("criterios en __no_aplica__ (veces, también en filas rechazadas):", dict(no_aplica.most_common()))
print("tiers de las propuestas que quedan:", dict(tiers))
print("controles:", "vacíos (como las mediciones 1-12)" if VACIOS else "los de ESPERADOS")


T = cfg["tiers"]
RANGOS = {"REVIEW": (T["review"], T["reply_needed"]),
          "READING_LATER": (T["reading_later"], T["review"]),
          "ARCHIVE": (None, T["reading_later"])}  # [desde, hasta)


def distancia(score, esperado):
    """Puntos que faltan (+) o sobran (-) para entrar en el rango del tier
    esperado; 0 si ya está dentro. None si no tiene rango (REPLY_NEEDED, que
    solo se alcanza con F)."""
    if esperado not in RANGOS:
        return None
    desde, hasta = RANGOS[esperado]
    if desde is not None and score < desde:
        return desde - score
    if hasta is not None and score >= hasta:
        return -(score - hasta + 1)
    return 0


def aciertos(con_f):
    filas = [(f["propuesta"]["tier"], ESPERADOS[int(f["id"]) - 1][0]) for f in r["resultados"]
             if f.get("propuesta") and ("F" in ESPERADOS[int(f["id"]) - 1][1]) == con_f]
    return sum(a == b for a, b in filas), len(filas)


for con_f, nombre in ((False, "sin F (mide al evaluador)"), (True, "con F (lo fija el control)")):
    ok, n = aciertos(con_f)
    print("aciertos de tier, %s: %d de %d propuestas" % (nombre, ok, n))
if len(CORREOS) > LOTE and not IDS:
    for desde, hasta in ((d + 1, min(d + LOTE, len(CORREOS))) for d in range(0, len(CORREOS), LOTE)):
        filas = [(f["propuesta"]["tier"], ESPERADOS[int(f["id"]) - 1][0]) for f in r["resultados"]
                 if f.get("propuesta") and desde <= int(f["id"]) <= hasta
                 and "F" not in ESPERADOS[int(f["id"]) - 1][1]]
        print("   correos %d-%d, sin F: %d de %d" % (desde, hasta, sum(a == b for a, b in filas), len(filas)))
if REPETIR > 1:
    print("por correo en %d repeticiones (tier score; - = sin propuesta):" % REPETIR)
    for ident, asunto, _, _ in SELECCION:
        vistas = []
        for rep in repeticiones:
            fila = next((f for x in rep for f in x["resultados"] if f["id"] == str(ident)), {})
            prop = fila.get("propuesta")
            vistas.append("%s %s" % (prop["tier"], prop["score"]) if prop else "-")
        esperado = ESPERADOS[ident - 1][0]
        bien = sum(v.split(" ")[0] == esperado for v in vistas)
        print("   [%s] esperado %-14s %d de %d | %s" % (ident, esperado, bien, REPETIR, ", ".join(vistas)))
confusion = collections.Counter(
    (ESPERADOS[int(f["id"]) - 1][0], f["propuesta"]["tier"]) for f in r["resultados"]
    if f.get("propuesta") and "F" not in ESPERADOS[int(f["id"]) - 1][1])
print("esperado -> propuesto (sin F):")
for (esperado, propuesto), n in sorted(confusion.items()):
    print("   %-14s -> %-14s %d%s" % (esperado, propuesto, n, "" if esperado == propuesto else "  ✗"))
fallos = [(f["id"], ESPERADOS[int(f["id"]) - 1][0], f["propuesta"]["score"]) for f in r["resultados"]
          if f.get("propuesta") and "F" not in ESPERADOS[int(f["id"]) - 1][1]
          and f["propuesta"]["tier"] != ESPERADOS[int(f["id"]) - 1][0]]
if fallos:
    print("fallos de tier (sin F): id, esperado, score, puntos hasta el rango esperado (+ faltan, - sobran):")
    for ident, esperado, score in fallos:
        print("   [%s] %-14s score %5s  %+g" % (ident, esperado, score, distancia(score, esperado)))



def criterios_por_eje(prop):
    """Líneas «eje (suma): criterio=veredicto ±puntos, ...» con los criterios
    que puntúan distinto de 0, el eje que más resta primero. La suma es antes
    de recortar el eje a su tope, así que puede no coincidir con `ejes`."""
    por_eje = collections.defaultdict(list)
    for c in prop.get("criterios") or []:
        if isinstance(c, dict) and c.get("puntos"):
            por_eje[c.get("eje")].append(c)
    lineas = []
    for eje, cs in sorted(por_eje.items(), key=lambda x: sum(c["puntos"] for c in x[1])):
        cs.sort(key=lambda c: c["puntos"])
        lineas.append("%s (%+g): %s" % (eje, sum(c["puntos"] for c in cs), ", ".join(
            "%s=%s %+g" % (c.get("criterio"), c.get("veredicto"), c["puntos"]) for c in cs)))
    return lineas


print()
print("=== detalle por correo (inventados) ===")
asuntos = {str(i + 1): a for i, (a, _, _) in enumerate(CORREOS)}
for f in r["resultados"]:
    fila = crudas.get(f["id"], {})
    crit = fila.get("criterios") or {}
    vacias = sorted(k for k, c in crit.items() if isinstance(c, dict)
                    and c.get("veredicto") != "__no_aplica__"
                    and not str(c.get("evidencia", "")).strip())
    salida, segundos = medidas.get(f["id"], (None, None))
    esperado = ESPERADOS[int(f["id"]) - 1][0]
    prop = f.get("propuesta") or {}
    tier = prop.get("tier")
    print("[%s] %s -> %s%s%s" % (f["id"], asuntos.get(f["id"]), f.get("motivo"),
          "" if tier is None else " | %s (esperado %s%s) score %s" % (
              tier, esperado, "" if tier == esperado else " ✗", prop.get("score")),
          "" if segundos is None else "  (%s tokens de salida, %d s)" % (salida, segundos)))
    if tier is not None and tier != esperado:
        print("     ejes:", prop.get("ejes"), "| reglas:", prop.get("hard_puntos"))
        for linea in criterios_por_eje(prop):
            print("       " + linea)
    for d in fila.get("dudas") or []:
        print("     duda:", str(d)[:220])
    if vacias:
        print("     evidencia vacía en:", ", ".join(vacias))
    if f.get("motivo") == "eco_distinto":
        texto = next(x["estado"]["texto"] for x in p["emails"] if x["id"] == f["id"])
        print("     eco esperado:", th.ancla_extracto(texto))
        print("     eco recibido:", fila.get("eco"))
