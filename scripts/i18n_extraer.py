#!/usr/bin/env python3
"""Extrae los literales visibles del original y genera i18n/es.yaml.

El texto de `es` NO se escribe a mano: el manifiesto (scripts/i18n_fuentes.yaml)
solo declara, por clave, un fichero y una expresión regular; el literal es el
grupo 1 de la ÚNICA coincidencia real en el fichero. Si no hay exactamente una,
falla. Las claves sin literal original (avisos, respuestas aceptadas) van en el
bloque `nuevas:` del manifiesto con origen «nuevo». Requiere PyYAML (herramienta
de desarrollo, no de runtime).
"""
import os
import re
import sys

import yaml

from i18n_baseline import quitar_bloques

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKILL_REL = "plugins/email-triage/skills/email-triage"
FICHEROS_VISIBLES = {"SKILL.md", "references/salidas-por-modo.md",
                     "references/manejo-errores.md", "references/paso-6-deshacer.md",
                     "references/paso-1c-hilos.md", "references/paso-2-calibracion.md",
                     "references/paso-5b-telemetria.md",
                     "references/paso-1-proveedores.md",
                     "references/paso-1-doctrina-ejecucion.md",
                     "references/interfaz-revision.md"}


class ErrorExtraccion(Exception):
    pass


def cargar_manifiesto(ruta):
    with open(ruta, encoding="utf-8") as f:
        man = yaml.safe_load(f) or {}
    for k in ("frases", "excluidos", "nuevas"):
        man.setdefault(k, [])
    return man


def _flags(patron):
    return re.MULTILINE | (re.DOTALL if patron.startswith("(?s)") else 0)


def sin_bloques_i18n(texto):
    """El original, sin los bloques `<!-- i18n:inicio -->`..`<!-- i18n:fin -->` añadidos.

    Las líneas de `fuente` se cuentan sobre este texto: apuntan al original y no se
    desplazan al insertar un bloque (ni un literal del bloque puede casar con un patrón).
    """
    return "\n".join(quitar_bloques(texto.split("\n")))


def _leer(raiz, fichero):
    with open(os.path.join(raiz, SKILL_REL, fichero), encoding="utf-8") as f:
        return sin_bloques_i18n(f.read())


def extraer(man, raiz=RAIZ):
    salida = {}
    for e in man["frases"]:
        clave = e["clave"]
        if clave in salida:
            raise ErrorExtraccion(f"{clave}: clave duplicada en el manifiesto")
        texto = _leer(raiz, e["fichero"])
        rx = re.compile(e["patron"], _flags(e["patron"]))
        if rx.groups < 1:
            raise ErrorExtraccion(f"{clave}: el patrón necesita un grupo de captura")
        ms = list(rx.finditer(texto))
        if len(ms) != 1:
            raise ErrorExtraccion(f"{clave}: {len(ms)} coincidencias (se espera 1) "
                                  f"en {e['fichero']}")
        literal = ms[0].group(1)
        if e.get("cita"):
            literal = "\n".join(re.sub(r"^> ?", "", l) for l in literal.split("\n"))
        if e.get("plano"):
            literal = re.sub(r"\s+", " ", literal).strip()
        n = texto.count("\n", 0, ms[0].start(1)) + 1
        salida[clave] = {"texto": literal, "origen": "original",
                         "fuente": f"{e['fichero']}:{n}",
                         "riesgo": e.get("riesgo", "normal"),
                         "lista": bool(e.get("lista", False)),
                         "invariable": bool(e.get("invariable", False))}
        if e.get("maquina"):
            salida[clave]["maquina"] = True
    for e in man["nuevas"]:
        clave = e["clave"]
        if clave in salida:
            raise ErrorExtraccion(f"{clave}: clave duplicada en el manifiesto")
        salida[clave] = {"texto": e["texto"], "origen": "nuevo", "fuente": "manifiesto",
                         "riesgo": e.get("riesgo", "normal"),
                         "lista": bool(e.get("lista", False)),
                         "invariable": bool(e.get("invariable", False))}
    return salida


def lineas_visibles(texto):
    """[(n, línea)] de bloques ``` SIN lenguaje y de citas `> ` (fuera de los bash)."""
    res, dentro, lenguaje = [], False, None
    for n, l in enumerate(texto.split("\n"), 1):
        if l.lstrip().startswith("```"):
            if not dentro:
                dentro, lenguaje = True, l.lstrip()[3:].strip()
            else:
                dentro, lenguaje = False, None
            continue
        if dentro and lenguaje == "":
            res.append((n, l))
        elif not dentro and l.startswith(">"):
            res.append((n, l))
    return res


def lineas_cubiertas(man, fichero, texto):
    """Números de línea cubiertos por frases o exclusiones de ese fichero."""
    cubiertas = set()
    for e in man["frases"] + man["excluidos"]:
        if fichero not in [e["fichero"], *e.get("tambien", [])]:
            continue
        rx = re.compile(e["patron"], _flags(e["patron"]))
        for m in rx.finditer(texto):
            ini = texto.count("\n", 0, m.start()) + 1
            fin = texto.count("\n", 0, m.end()) + 1
            cubiertas.update(range(ini, fin + 1))
    return cubiertas


def generar_es(raiz=RAIZ, destino=None):
    man = cargar_manifiesto(os.path.join(raiz, "scripts", "i18n_fuentes.yaml"))
    frases = extraer(man, raiz)
    destino = destino or os.path.join(raiz, SKILL_REL, "i18n", "es.yaml")
    os.makedirs(os.path.dirname(destino), exist_ok=True)
    doc = {"estado": "referencia", "redactado_por": "original del proyecto",
           "revisado_por": "autor del proyecto", "frases": frases}
    with open(destino, "w", encoding="utf-8") as f:
        f.write("# GENERADO por scripts/i18n_extraer.py — no editar a mano.\n")
        yaml.safe_dump(doc, f, allow_unicode=True, sort_keys=False, width=1000)
    print(f"OK: {len(frases)} frases -> {destino}")


if __name__ == "__main__":
    if sys.argv[1:] == ["generar"]:
        generar_es()
    else:
        print("uso: i18n_extraer.py generar")
        sys.exit(2)
