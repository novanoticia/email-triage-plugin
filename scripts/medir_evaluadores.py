#!/usr/bin/env python3
"""Mide por qué las filas de `hibrido` vuelven al principal (evaluadores LLM).

Herramienta de desarrollo (no se distribuye con el plugin). Envía 40 correos
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
    PROVEEDOR=ollama PAUSA=0 python3 scripts/medir_evaluadores.py  # ~75 min

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
"""
import collections
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

VACIOS = os.environ.get("CONTROLES", "") == "vacios"

cfg = yaml.safe_load(open("plugins/email-triage/skills/email-triage/config.yaml", encoding="utf-8"))
p = ev.preparar({"perfil_minimo": PERFIL, "emails": [
    {"id": str(i + 1), "asunto": a, "remitente": r, "cuerpo": c}
    for i, (a, r, c) in enumerate(CORREOS)]})
for e in p["emails"]:
    e["control"] = control("" if VACIOS else ESPERADOS[int(e["id"]) - 1][1])
    e["contexto_suficiente"] = True

capa = {"activo": True, "acepta_envio_datos": True, "modo": "hibrido",
        "proveedor": PROVEEDOR, "max_llamadas": len(CORREOS),
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
print("Enviando %d correos inventados a %s (unos %d s)..." % (len(CORREOS), PROVEEDOR, int(len(CORREOS) * PAUSA)))
r = ev.evaluar(p, cfg, capa, capturar)

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
print("filas con dudas anotadas (también las rechazadas):", con_dudas, "de", len(CORREOS))
print("propuestas (validadas + a reevaluar):", sum("propuesta" in f for f in r["resultados"]), "de", len(CORREOS))
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
    for d in fila.get("dudas") or []:
        print("     duda:", str(d)[:220])
    if vacias:
        print("     evidencia vacía en:", ", ".join(vacias))
    if f.get("motivo") == "eco_distinto":
        texto = next(x["estado"]["texto"] for x in p["emails"] if x["id"] == f["id"])
        print("     eco esperado:", th.ancla_extracto(texto))
        print("     eco recibido:", fila.get("eco"))
