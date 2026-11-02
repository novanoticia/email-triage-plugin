#!/usr/bin/env python3
"""Vuelve a puntuar veredictos guardados con otra configuración de scoring.

Herramienta de desarrollo (no se distribuye con el plugin). Lee el fichero que
escribe `GUARDAR=RUTA python3 scripts/medir_evaluadores.py` (veredictos de
los correos INVENTADOS del banco, sin texto de ningún correo) y recalcula
score y tier con `triage_helpers.cmd_scoring_dispatch`, primero con el config
plantilla tal cual y después con cada variante. Así se mide un cambio de
pesos, de ejes o de rangos sobre los 120 correos sin volver a llamar al
proveedor: los veredictos son los mismos, solo cambia la aritmética.

No llama a ninguna red, no escribe nada y no toca ~/.email-triage. Uso, desde
la raíz del repositorio:

    python3 scripts/simular_scoring.py RUTA                  # variantes de serie
    python3 scripts/simular_scoring.py RUTA --eje relevancia_longitudinal=calidad_epistemica
    python3 scripts/simular_scoring.py RUTA --rango valor_decisional=-5,10

Las variantes de serie son las de la opción 2 de
docs/auditoria-reading-later.md. Con `--eje` o `--rango` se simula solo la
variante que describan (se pueden repetir y combinar).

Lo que no mide: un cambio de redacción de un criterio (cambiaría los
veredictos, y eso exige otra medición con el proveedor).
"""
import argparse
import collections
import copy
import json
import os
import re
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(RAIZ, "plugins/email-triage/skills/email-triage/scripts"))
import triage_helpers as th  # noqa: E402

CONFIG = os.path.join(RAIZ, "plugins/email-triage/skills/email-triage/config.yaml")
FORMATO = 1
TIERS = ("REPLY_NEEDED", "REVIEW", "READING_LATER", "ARCHIVE")

# Opción 2 de docs/auditoria-reading-later.md: sacar los criterios de interés
# del eje recortado a [0, 10].
VARIANTES = [
    ("opción 2a: relevancia_longitudinal a calidad_epistemica",
     {"eje": {"relevancia_longitudinal": "calidad_epistemica"}}),
    ("opción 2b: relevancia_longitudinal y abre_opciones a calidad_epistemica",
     {"eje": {"relevancia_longitudinal": "calidad_epistemica",
              "abre_opciones": "calidad_epistemica"}}),
]


def filas_guardables(repeticiones, esperados):
    """Lo que se guarda de una medición: por pasada, una fila por correo con
    propuesta (`payload_scoring`: controles y veredictos, nunca texto).

    `repeticiones`: lista de pasadas; cada una, lista de salidas de
    `evaluadores.evaluar` (una por lote). `esperados`: ESPERADOS del banco.
    Las filas sin `payload_scoring` (eco distinto, plantilla, error) no se
    guardan: no tienen veredictos aceptados."""
    pasadas = []
    for rep in repeticiones:
        filas = []
        for salida in rep:
            for f in salida.get("resultados") or []:
                carga = f.get("payload_scoring")
                prop = f.get("propuesta") or {}
                if not isinstance(carga, dict) or not prop:
                    continue
                esperado, letras = esperados[int(f["id"]) - 1]
                filas.append({"id": str(f["id"]), "esperado": esperado, "controles": letras,
                              "payload": carga, "tier": prop.get("tier"),
                              "score": prop.get("score")})
        pasadas.append(filas)
    return pasadas


def guardar(ruta, proveedor, repeticiones, esperados):
    """Escribe el fichero de veredictos (JSON). Devuelve cuántas filas guardó."""
    pasadas = filas_guardables(repeticiones, esperados)
    version = re.search(r"\(v([\d.]+)\)", th.__doc__ or "")
    datos = {"formato": FORMATO, "proveedor": proveedor,
             "version": "v" + version.group(1) if version else None,
             "pasadas": pasadas}
    with open(ruta, "w", encoding="utf-8") as fh:
        json.dump(datos, fh, ensure_ascii=False, indent=1)
    return sum(len(p) for p in pasadas)


def cargar(ruta):
    with open(ruta, encoding="utf-8") as fh:
        datos = json.load(fh)
    if not isinstance(datos, dict) or datos.get("formato") != FORMATO:
        raise ValueError("no es un fichero de veredictos de medir_evaluadores.py (formato %s)"
                         % FORMATO)
    return datos


def aplicar(cfg, variante):
    """Copia del config con la variante: {"eje": {criterio: eje},
    "rango": {eje: [lo, hi]}}. Un criterio o un eje desconocido es error: una
    errata no debe simular en silencio el config sin cambios."""
    cfg = copy.deepcopy(cfg)
    criterios = cfg["criterios_epistemicos"]
    ejes = cfg["scoring"]["ejes"]
    for crit, eje in (variante.get("eje") or {}).items():
        if crit not in criterios:
            raise ValueError("criterio desconocido: %s" % crit)
        if eje not in ejes:
            raise ValueError("eje desconocido: %s" % eje)
        criterios[crit]["eje"] = eje
    for eje, rango in (variante.get("rango") or {}).items():
        if eje not in ejes:
            raise ValueError("eje desconocido: %s" % eje)
        ejes[eje] = list(rango)
    return cfg


def puntuar(filas, cfg):
    """{id: (tier, score)} con este config."""
    salida = {}
    for f in filas:
        r = th.cmd_scoring_dispatch(dict(f["payload"]), cfg)
        salida[f["id"]] = (r.get("tier"), r.get("score"))
    return salida


def resumen(filas, puntos):
    """Aciertos sin F, por tier esperado, y matriz esperado -> obtenido."""
    sin_f = [f for f in filas if "F" not in f["controles"]]
    por_tier = collections.defaultdict(lambda: [0, 0])
    confusion = collections.Counter()
    for f in sin_f:
        obtenido = puntos[f["id"]][0]
        por_tier[f["esperado"]][1] += 1
        por_tier[f["esperado"]][0] += obtenido == f["esperado"]
        confusion[(f["esperado"], obtenido)] += 1
    return sum(v[0] for v in por_tier.values()), len(sin_f), dict(por_tier), confusion


def informe(filas, cfg, variantes, salida=print):
    base = puntuar(filas, cfg)
    distintas = [f["id"] for f in filas if base[f["id"]][0] != f["tier"]]
    salida("filas: %d | sin F: %d" % (len(filas), sum("F" not in f["controles"] for f in filas)))
    if distintas:
        salida("AVISO: con el config actual %d filas no dan el tier de la medición (%s): el "
               "config ha cambiado desde que se guardó" % (len(distintas), ", ".join(distintas)))
    for nombre, puntos in [("config actual", base)] + [
            (n, puntuar(filas, aplicar(cfg, v))) for n, v in variantes]:
        ok, n, por_tier, confusion = resumen(filas, puntos)
        salida("")
        salida("== %s: %d de %d sin F" % (nombre, ok, n))
        salida("   por tier esperado: " + ", ".join(
            "%s %d de %d" % (t, por_tier[t][0], por_tier[t][1]) for t in TIERS if t in por_tier))
        salida("   fallos: " + (", ".join("%s -> %s %d" % (e, o, k) for (e, o), k in sorted(
            confusion.items()) if e != o) or "ninguno"))
        if puntos is base:
            continue
        cambios = [f for f in filas if puntos[f["id"]] != base[f["id"]]
                   and "F" not in f["controles"]]
        cambian_tier = [f for f in cambios if puntos[f["id"]][0] != base[f["id"]][0]]
        salida("   cambian de score: %d; de tier: %d" % (len(cambios), len(cambian_tier)))
        for f in cambian_tier:
            antes, ahora = base[f["id"]], puntos[f["id"]]
            marca = ("✓" if ahora[0] == f["esperado"] else
                     "✗ (antes bien)" if antes[0] == f["esperado"] else "✗")
            salida("   [%s] esperado %-13s %s %s -> %s %s  %s" % (
                f["id"], f["esperado"], antes[0], antes[1], ahora[0], ahora[1], marca))


def _par(texto, tipo):
    clave, sep, valor = texto.partition("=")
    if not sep or not clave or not valor:
        raise argparse.ArgumentTypeError("se esperaba CLAVE=VALOR: %r" % texto)
    if tipo == "rango":
        try:
            lo, hi = (int(x) for x in valor.split(","))
        except ValueError:
            raise argparse.ArgumentTypeError("rango no válido (ej. -5,10): %r" % valor)
        if lo > hi:
            raise argparse.ArgumentTypeError("rango invertido: %r" % valor)
        return clave, [lo, hi]
    return clave, valor


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("ruta", help="fichero escrito con GUARDAR=RUTA")
    ap.add_argument("--eje", action="append", default=[], type=lambda t: _par(t, "eje"),
                    metavar="CRITERIO=EJE")
    ap.add_argument("--rango", action="append", default=[], type=lambda t: _par(t, "rango"),
                    metavar="EJE=LO,HI")
    ap.add_argument("--pasada", type=int, default=0,
                    help="qué pasada simular si se guardaron varias (0 = la primera)")
    args = ap.parse_args(argv)
    import yaml
    with open(CONFIG, encoding="utf-8") as fh:
        cfg = yaml.safe_load(fh)
    try:
        datos = cargar(args.ruta)
        pasadas = datos["pasadas"]
        if not 0 <= args.pasada < len(pasadas):
            raise ValueError("solo hay %d pasadas" % len(pasadas))
        variantes = VARIANTES
        if args.eje or args.rango:
            variante = {"eje": dict(args.eje), "rango": dict(args.rango)}
            nombre = "variante: " + ", ".join(["%s a %s" % x for x in args.eje]
                                              + ["%s en %s" % x for x in args.rango])
            variantes = [(nombre, variante)]
        for _, v in variantes:
            aplicar(cfg, v)  # valida antes de imprimir nada
    except (OSError, ValueError, KeyError) as e:
        print("error: %s" % e, file=sys.stderr)
        return 2
    print("veredictos de %s (%s), pasada %d de %d" % (
        datos.get("proveedor"), datos.get("version"), args.pasada + 1, len(pasadas)))
    informe(pasadas[args.pasada], cfg, variantes)
    return 0


if __name__ == "__main__":
    sys.exit(main())
