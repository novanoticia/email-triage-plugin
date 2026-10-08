#!/usr/bin/env python3
"""Línea base del idioma por defecto: hash por línea de los ficheros originales.

Se genera en el commit base y se compara tras cada tarea. La base solo se mueve
cuando el original en español cambia A PROPÓSITO (v3.15.0: interfaz de revisión;
antes 2c98507), en un commit propio que lo explique:
quitando los bloques `<!-- i18n:inicio -->`..`<!-- i18n:fin -->` (más la línea en
blanco que los sigue), cada fichero original debe tener las mismas líneas.
Los tokens de versión se normalizan: el bump de versión es la única excepción.
"""
import fnmatch
import glob
import hashlib
import json
import os
import re
import subprocess
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKILL = "plugins/email-triage/skills/email-triage"
RUTA_BASE = os.path.join(RAIZ, "tests", "i18n", "linea_base.json")
INI = "<!-- i18n:inicio -->"
FIN = "<!-- i18n:fin -->"
COMMIT_BASE = "9cc7bc3"   # v3.15.0; antes 2c98507 (v3.13.5)
# Lookarounds en vez de \b: «v3.13» no tiene límite de palabra entre «v» y «3».
# Cualquier parche (3.14.N) se normaliza: enumerar parches ([05], [015]…) rompía la
# línea base en cada bump. El menor se acota a 3.1x (13, 14, 15…) a propósito.
_RE_VERSION = re.compile(r"(?<![\d.])3\.1\d(?:\.\d+)?(?!\d)")
PATRONES = [f"{SKILL}/SKILL.md", f"{SKILL}/config.yaml", f"{SKILL}/config-veloz.yaml",
            "plugins/email-triage/commands/triage.md",
            f"{SKILL}/references/*", f"{SKILL}/scripts/*.py"]


def _git(*args):
    return subprocess.run(["git", *args], cwd=RAIZ, check=True, capture_output=True).stdout


def listar_ficheros(commit=None):
    """Ficheros del original que se vigilan: en el árbol de trabajo o en un commit."""
    if commit is None:
        salida = []
        for p in PATRONES:
            salida += sorted(os.path.relpath(f, RAIZ) for f in glob.glob(os.path.join(RAIZ, p)))
        return salida
    nombres = _git("ls-tree", "-r", "--name-only", commit).decode("utf-8").splitlines()
    return sorted(n for n in nombres if any(fnmatch.fnmatchcase(n, p) for p in PATRONES))


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


def hash_linea(linea):
    return hashlib.sha1(_RE_VERSION.sub("<V>", linea).encode("utf-8")).hexdigest()


def hashes_de_texto(texto):
    return [hash_linea(l) for l in quitar_bloques(texto.split("\n"))]


def hashes_de(ruta):
    with open(ruta, encoding="utf-8") as f:
        return hashes_de_texto(f.read())


def calcular(commit=None):
    """Hashes por línea del árbol de trabajo o, con `commit`, del original en ese commit."""
    base = {"commit_base": commit or COMMIT_BASE, "ficheros": {}}
    for rel in listar_ficheros(commit):
        if commit is None:
            base["ficheros"][rel] = hashes_de(os.path.join(RAIZ, rel))
        else:
            base["ficheros"][rel] = hashes_de_texto(_git("show", f"{commit}:{rel}").decode("utf-8"))
    return base


def generar():
    """La línea base sale SIEMPRE del commit base (git), no del árbol de trabajo."""
    base = calcular(commit=COMMIT_BASE)
    os.makedirs(os.path.dirname(RUTA_BASE), exist_ok=True)
    with open(RUTA_BASE, "w", encoding="utf-8") as f:
        json.dump(base, f, indent=0)
    print(f"OK: línea base de {len(base['ficheros'])} ficheros (commit {COMMIT_BASE}) -> {RUTA_BASE}")


if __name__ == "__main__":
    if sys.argv[1:] == ["generar"]:
        generar()
    else:
        print("uso: i18n_baseline.py generar")
        sys.exit(2)
