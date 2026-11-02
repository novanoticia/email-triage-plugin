#!/usr/bin/env python3
"""Cuenta cómo se reparten por tier y por score los correos reales ya puntuados.

Herramienta de desarrollo (no se distribuye con el plugin). Responde a la
pregunta de las mediciones 16 y 17: ¿cuántos correos reales caen en
`ARCHIVE` a pocos puntos de `READING_LATER`, y por qué?

SOLO LEE los desgloses que escribe `scoring --desglose-append`
(`~/.email-triage/desgloses/*.jsonl`) y el umbral de tu config. No escribe
nada, no envía nada a ninguna API y no imprime asuntos, remitentes, ids ni
texto: solo recuentos. Uso, desde la raíz del repositorio:

    python3 scripts/distribucion_tiers.py
    python3 scripts/distribucion_tiers.py RUTA [RUTA ...]   # otros desgloses

Cada correo cuenta una vez por sesión, con su última pasada (la misma regla
que `diagnostico-ejes`).
"""
import collections
import glob
import os
import sys

sys.path.insert(0, "plugins/email-triage/skills/email-triage/scripts")
import triage_helpers as th  # noqa: E402

# Tramos de score dentro de ARCHIVE (desde, hasta), ambos inclusive.
TRAMOS_ARCHIVE = ((-2, -1), (-5, -3), (-10, -6), (None, -11))
# Umbrales de READING_LATER que se simulan (el actual de la plantilla es 0).
UMBRALES = (0, -1, -2, -3, -5)
EJES_QUE_SOLO_RESTAN = ("riesgo_manipulacion", "coste_cognitivo")


def _num(x):
    return isinstance(x, (int, float)) and not isinstance(x, bool)


def _en_tramo(score, tramo):
    desde, hasta = tramo
    return (desde is None or score >= desde) and score <= hasta


def _otras_penalizaciones(r):
    """True si el correo pierde puntos por algo que no es `calidad_epistemica`:
    riesgo, coste, reglas duras o puntos extra negativos."""
    ejes = r.get("ejes") if isinstance(r.get("ejes"), dict) else {}
    if any(_num(ejes.get(e)) and ejes[e] < 0 for e in EJES_QUE_SOLO_RESTAN):
        return True
    return any(_num(r.get(k)) and r[k] < 0 for k in ("hard_puntos", "extra_points"))


def distribucion(resultados, umbral_actual):
    """Recuentos a partir de resultados de scoring (sin texto). Función pura."""
    validos = [r for r in resultados if isinstance(r, dict)
               and _num(r.get("score")) and isinstance(r.get("tier"), str)]
    tiers = collections.Counter(r["tier"] for r in validos)
    archive = [r for r in validos if r["tier"] == "ARCHIVE"]
    tramos = []
    for tramo in TRAMOS_ARCHIVE:
        dentro = [r for r in archive if _en_tramo(r["score"], tramo)]
        tramos.append({"tramo": tramo, "correos": len(dentro),
                       "con_otras_penalizaciones": sum(map(_otras_penalizaciones, dentro))})
    # Solo los ARCHIVE por score (no por un cap): los que tienen el score por
    # debajo del umbral actual. Un umbral más bajo los pasaría a READING_LATER.
    pasarian = {u: sum(1 for r in archive if u <= r["score"] < umbral_actual)
                for u in UMBRALES if u < umbral_actual}
    return {"correos": len(validos), "ignorados": len(resultados) - len(validos),
            "tiers": dict(tiers), "tramos_archive": tramos,
            "pasarian_a_reading_later": pasarian}


def _umbral_config():
    for ruta in (os.path.join(th.base_estado(), "config.yaml"),
                 "plugins/email-triage/skills/email-triage/config.yaml"):
        if not os.path.isfile(ruta):
            continue  # `_cargar_config` cae a la plantilla y el origen mentiría
        try:
            cfg = th._cargar_config(ruta)
        except (th.ConfigError, SystemExit, OSError):
            continue
        valor = (cfg.get("tiers") or {}).get("reading_later") if isinstance(cfg, dict) else None
        if _num(valor):
            return valor, ruta
    return 0, "por defecto"


def _leer(rutas):
    resultados, fallos = [], 0
    for ruta in rutas:
        try:
            with open(ruta, encoding="utf-8") as fh:
                doc = th._parsear_desglose(fh.read(th.MAX_INGESTA_BYTES))
        except (OSError, ValueError):
            fallos += 1
            continue
        pasadas = doc.get("pasadas") if isinstance(doc, dict) and "pasadas" in doc else [doc]
        resultados.extend(th._ultima_pasada(pasadas, ruta, []))
    return resultados, fallos


def main(argv):
    rutas = argv or sorted(glob.glob(os.path.join(th.base_estado(), "desgloses", "*.jsonl")))
    if not rutas:
        print("No hay desgloses en", os.path.join(th.base_estado(), "desgloses"),
              "(se escriben con scoring --desglose-append).")
        return 1
    umbral, origen = _umbral_config()
    resultados, fallos = _leer(rutas)
    d = distribucion(resultados, umbral)
    print("desgloses leídos: %d (ilegibles: %d) | correos: %d (sin score o tier: %d)"
          % (len(rutas) - fallos, fallos, d["correos"], d["ignorados"]))
    print("umbral de READING_LATER: %s (%s)" % (umbral, origen))
    print("tiers:")
    for tier in ("REPLY_NEEDED", "REVIEW", "READING_LATER", "ARCHIVE"):
        n = d["tiers"].get(tier, 0)
        print("   %-14s %4d  (%.0f %%)" % (tier, n, 100.0 * n / d["correos"] if d["correos"] else 0))
    print("ARCHIVE por tramo de score (con otras penalizaciones = riesgo, coste o reglas):")
    for t in d["tramos_archive"]:
        desde, hasta = t["tramo"]
        nombre = "%s a %s" % (desde, hasta) if desde is not None else "%s o menos" % hasta
        print("   %-12s %4d  (con otras penalizaciones: %d)"
              % (nombre, t["correos"], t["con_otras_penalizaciones"]))
    print("con otro umbral de READING_LATER pasarían de ARCHIVE a READING_LATER:")
    for u, n in sorted(d["pasarian_a_reading_later"].items(), reverse=True):
        print("   umbral %3s -> %4d" % (u, n))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
