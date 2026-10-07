#!/usr/bin/env python3
"""Línea base del idioma por defecto: hash por línea de los ficheros originales.

Se genera UNA vez, en el commit base (2c98507), y se compara tras cada tarea:
quitando los bloques `<!-- i18n:inicio -->`..`<!-- i18n:fin -->` (más la línea en
blanco que los sigue), cada fichero original debe tener las mismas líneas.
Los tokens de versión se normalizan: el bump de versión es la única excepción.
"""
import glob
import hashlib
import json
import os
import re
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKILL = "plugins/email-triage/skills/email-triage"
RUTA_BASE = os.path.join(RAIZ, "tests", "i18n", "linea_base.json")
INI = "<!-- i18n:inicio -->"
FIN = "<!-- i18n:fin -->"
_RE_VERSION = re.compile(r"\b3\.1[34](?:\.[05])?\b")


def listar_ficheros():
    pats = [f"{SKILL}/SKILL.md", f"{SKILL}/config.yaml", f"{SKILL}/config-veloz.yaml",
            "plugins/email-triage/commands/triage.md",
            f"{SKILL}/references/*", f"{SKILL}/scripts/*.py"]
    salida = []
    for p in pats:
        salida += sorted(os.path.relpath(f, RAIZ) for f in glob.glob(os.path.join(RAIZ, p)))
    return salida


FICHEROS = listar_ficheros()


def quitar_bloques(lineas):
    """Quita cada bloque i18n y UNA línea en blanco posterior. Falla si está desbalanceado."""
    salida, i = [], 0
    while i < len(lineas):
        if lineas[i].strip() == INI:
            j = i + 1
            while j < len(lineas) and lineas[j].strip() != FIN:
                if lineas[j].strip() == INI:
                    raise ValueError("bloque i18n anidado")
                j += 1
            if j >= len(lineas):
                raise ValueError("bloque i18n sin cerrar")
            i = j + 1
            if i < len(lineas) and lineas[i].strip() == "":
                i += 1
            continue
        if lineas[i].strip() == FIN:
            raise ValueError("marcador de fin sin inicio")
        salida.append(lineas[i])
        i += 1
    return salida


def hashes_de(ruta):
    with open(ruta, encoding="utf-8") as f:
        lineas = f.read().split("\n")
    lineas = quitar_bloques(lineas)
    return [hashlib.sha1(_RE_VERSION.sub("<V>", l).encode("utf-8")).hexdigest()
            for l in lineas]


def generar():
    base = {"commit_base": "2c98507", "ficheros": {}}
    for rel in FICHEROS:
        base["ficheros"][rel] = hashes_de(os.path.join(RAIZ, rel))
    os.makedirs(os.path.dirname(RUTA_BASE), exist_ok=True)
    with open(RUTA_BASE, "w", encoding="utf-8") as f:
        json.dump(base, f, indent=0)
    print(f"OK: línea base de {len(base['ficheros'])} ficheros -> {RUTA_BASE}")


if __name__ == "__main__":
    if sys.argv[1:] == ["generar"]:
        generar()
    else:
        print("uso: i18n_baseline.py generar")
        sys.exit(2)
