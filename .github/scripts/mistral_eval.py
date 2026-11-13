#!/usr/bin/env python3
"""Evaluación del revisor de Mistral con casos reales del historial.

Responde a una pregunta que los tests no pueden responder: ¿encuentra el
revisor defectos de verdad, y cuántos hallazgos falsos repite? (propuesta 2
de docs/auditoria-mistral-2026-10-29.md).

Cada caso fija dos commits del historial y se revisa con el MISMO código que
un PR (diff, contexto, prompt, llamada y validación de mistral_review.py):

- positivo: `cabeza` es un commit con un defecto conocido y `arreglo` el
  commit que lo corrigió. El objetivo se deriva solo: las funciones de
  `cabeza` que el arreglo tocó. Un hallazgo «señala la función» si cita una
  línea del diff dentro de una de ellas.
- negativo: `cabeza` es un commit sobre el que Mistral publicó hallazgos que
  la auditoría contrastó como falsos, y `archivos` dónde estaban. Se cuentan
  los hallazgos y cuántos caen otra vez en esos archivos.

Lo que mide es mecánico (dónde apunta un hallazgo). Que el hallazgo describa
el defecto real lo decide una persona: el informe lista cada hallazgo para
etiquetarlo. Señalar la función no prueba acertar; no señalarla sí indica que
el defecto no se vio.

Diferencias con una revisión real, a propósito: el título es el asunto del
commit y no hay descripción (la del PR histórico podía nombrar el arreglo), y
la guía es la del árbol actual, no la de entonces.

Solo stdlib. Sin `--ejecutar` no llama a la API: lista casos y objetivos.
"""
import argparse
import importlib.util
import json
import os
import re
import subprocess
import sys
import urllib.error

_AQUI = os.path.dirname(os.path.abspath(__file__))
_spec = importlib.util.spec_from_file_location(
    "mistral_review", os.path.join(_AQUI, "mistral_review.py"))
mr = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mr)

CASOS = os.path.join(os.path.dirname(_AQUI), "eval", "casos.json")
MAX_LLAMADAS = 80  # tope de solicitudes por ejecución: cada una cuesta dinero


def git(*args):
    return subprocess.run(("git",) + args, check=True, capture_output=True,
                          text=True, encoding="utf-8", errors="replace").stdout


def cargar_casos(ruta):
    """Lee y valida el fichero de casos; un caso mal escrito no se evalúa a medias."""
    with open(ruta, encoding="utf-8") as fh:
        casos = json.load(fh)
    vistos = set()
    for c in casos:
        if not isinstance(c, dict) or c.get("tipo") not in ("positivo", "negativo"):
            raise ValueError("caso sin tipo válido: %r" % (c,))
        claves = ["id", "base", "cabeza", "defecto"] + (
            ["arreglo"] if c["tipo"] == "positivo" else ["archivos"])
        for clave in claves:
            if not c.get(clave):
                raise ValueError("caso %s: falta %s" % (c.get("id"), clave))
        for clave in ("base", "cabeza", "arreglo"):
            # SHA completo y nada más: `$` admitiría un salto de línea final.
            if clave in c and not re.fullmatch(r"[0-9a-f]{40}", str(c[clave])):
                raise ValueError("caso %s: %s no es un SHA completo" % (c["id"], clave))
        if c["id"] in vistos:
            raise ValueError("caso repetido: %s" % c["id"])
        vistos.add(c["id"])
    return casos


def objetivos(caso):
    """{archivo: [(inicio, fin, nombre)]} donde debería caer un hallazgo.

    Positivo: funciones de `cabeza` (código Python, no tests) que el arreglo
    tocó. Se calcula con el diff al revés (arreglo → cabeza), cuyo lado nuevo
    es la cabeza. Negativo: los archivos enteros de los hallazgos falsos.
    """
    if caso["tipo"] == "negativo":
        return {archivo: [] for archivo in caso["archivos"]}
    inverso = git("-c", "core.quotePath=true", "diff", "--no-color", "--no-ext-diff",
                  "--no-textconv", "--src-prefix=a/", "--dst-prefix=b/", "-U0",
                  caso["arreglo"], caso["cabeza"], "--", ".")
    destino = {}
    for archivo, lineas in sorted(mr.lineas_cambiadas(inverso).items()):
        if (not archivo.endswith(".py") or mr._es_test(archivo)
                or archivo in caso.get("ignorar", ())):
            continue  # `ignorar`: lo que el arreglo tocó sin ser el defecto
        try:
            texto = git("show", "%s:%s" % (caso["cabeza"], archivo))
        except subprocess.CalledProcessError:
            continue  # el arreglo creó el archivo: en la cabeza no hay dónde apuntar
        rangos = mr._rangos_python(texto, lineas)
        if rangos:
            destino[archivo] = rangos
    return destino


def lineas_citadas(diff, archivo, fragmento):
    """Números de línea (en la cabeza) de las líneas del diff que cita un fragmento."""
    citadas = set()
    for linea in str(fragmento).splitlines():
        limpio = linea.strip()
        if any(c.isalnum() for c in limpio):
            citadas.add(limpio)
            if limpio[:1] in "+-":
                citadas.add(limpio[1:].strip())
    numeros = set()
    for ruta, linea, numero in mr._lineas_de_hunks(diff):
        if ruta == archivo and not linea.startswith("-") and linea[1:].strip() in citadas:
            numeros.add(numero)
    return numeros


def clasificar(hallazgo, diff, destino):
    """'funcion' si cita una línea dentro de un objetivo; 'archivo'; o 'fuera'."""
    rangos = destino.get(hallazgo["archivo"])
    if rangos is None:
        return "fuera"
    numeros = lineas_citadas(diff, hallazgo["archivo"], hallazgo["fragmento"])
    if any(inicio <= n <= fin for n in numeros for inicio, fin, _ in rangos):
        return "funcion"
    return "archivo"


def revisar(caso, modelo, clave):
    """Una revisión del caso, igual que main(): devuelve un registro sin texto libre
    del modelo salvo los hallazgos y pendientes ya validados."""
    diff = mr.obtener_diff(caso["base"], caso["cabeza"])
    titulo = git("log", "-1", "--format=%s", caso["cabeza"]).strip()
    mensajes, recortado = mr.construir_mensajes(
        titulo, None, diff, mr.leer_guia(),
        mr.obtener_contexto(diff[:mr.MAX_DIFF], caso["cabeza"]))
    rutas = mr.obtener_rutas_diff(caso["base"], caso["cabeza"])
    registro = {"estado": "invalida", "detalle": "", "solicitudes": 0,
                "recortado": recortado, "hallazgos": [], "pendientes": []}
    try:
        for _ in range(mr.INTENTOS_RESPUESTA):
            registro["solicitudes"] += 1
            texto = mr.llamar_mistral(mensajes, modelo, clave)
            diagnostico = []
            resultado = mr.interpretar(texto, diff[:mr.MAX_DIFF],
                exigir_comprobaciones=True, rutas_comprobaciones=rutas,
                diagnostico=diagnostico)
            registro["detalle"] = ", ".join(diagnostico)
            if resultado is not None:
                break
    except urllib.error.HTTPError as fallo:
        registro.update(estado="error", detalle="HTTP %d" % fallo.code)
        return registro
    except (urllib.error.URLError, TimeoutError):
        registro.update(estado="error", detalle="conexión")
        return registro
    except ValueError as fallo:
        registro.update(estado="cortada", detalle=getattr(fallo, "causa", "") or "incompleta")
        return registro
    if resultado is None:
        return registro
    destino = objetivos(caso)
    registro["estado"] = "valida"
    for h in resultado[1]:
        registro["hallazgos"].append({
            "severidad": h["severidad"], "archivo": h["archivo"],
            "problema": mr._linea(h["problema"], 400),
            "donde": clasificar(h, diff[:mr.MAX_DIFF], destino)})
    for c in json.loads(texto)["comprobaciones"]:
        if c["estado"] == "pendiente":
            registro["pendientes"].append({
                "archivo": c["archivo"], "escenario": mr._linea(c["escenario"], 300),
                "donde": "archivo" if c["archivo"] in destino else "fuera"})
    return registro


def resumir(casos, resultados, modelo, repeticiones):
    """Informe en Markdown. Las cifras son recuentos; el juicio final es humano."""
    partes = ["## Evaluación del revisor de Mistral (`%s`, %d repetición(es) por caso)"
              % (modelo, repeticiones), ""]
    ejecuciones = [r for c in casos for r in resultados[c["id"]]]
    validas = [r for r in ejecuciones if r["estado"] == "valida"]
    partes.append("- **Revisiones válidas:** %d de %d (%s)." % (
        len(validas), len(ejecuciones), ", ".join(
            "%s: %d" % (e, sum(r["estado"] == e for r in ejecuciones))
            for e in ("invalida", "cortada", "error")
            if any(r["estado"] == e for r in ejecuciones)) or "sin fallos"))
    positivos = [c for c in casos if c["tipo"] == "positivo"]
    negativos = [c for c in casos if c["tipo"] == "negativo"]

    def senala(r):
        return any(h["donde"] == "funcion" for h in r["hallazgos"])

    if positivos:
        alguna = sum(any(senala(r) for r in resultados[c["id"]]) for c in positivos)
        ok = [r for c in positivos for r in resultados[c["id"]] if r["estado"] == "valida"]
        partes.append("- **Defectos reales:** en %d de %d casos algún hallazgo señala la "
                      "función que luego se corrigió; en %d de %d revisiones válidas."
                      % (alguna, len(positivos), sum(senala(r) for r in ok), len(ok)))
    if negativos:
        ok = [r for c in negativos for r in resultados[c["id"]] if r["estado"] == "valida"]
        total = sum(len(r["hallazgos"]) for r in ok)
        repite = sum(h["donde"] != "fuera" for r in ok for h in r["hallazgos"])
        partes.append("- **Commits con hallazgos falsos conocidos:** %d hallazgo(s) en %d "
                      "revisiones válidas; %d en los mismos archivos que entonces."
                      % (total, len(ok), repite))
    partes += ["", "Señalar la función no prueba acertar: etiqueta cada hallazgo de abajo.",
               "", "| Caso | Tipo | Válidas | Señala la función | Hallazgos | Pendientes |",
               "|---|---|---:|---:|---:|---:|"]
    for c in casos:
        rs = resultados[c["id"]]
        ok = [r for r in rs if r["estado"] == "valida"]
        partes.append("| `%s` | %s | %d/%d | %s | %d | %d |" % (
            c["id"], c["tipo"], len(ok), len(rs),
            "%d/%d" % (sum(senala(r) for r in ok), len(ok))
            if c["tipo"] == "positivo" else "—",
            sum(len(r["hallazgos"]) for r in ok), sum(len(r["pendientes"]) for r in ok)))
    partes += ["", "### Hallazgos para etiquetar"]
    for c in casos:
        partes += ["", "**`%s`** (%s) — %s" % (c["id"], c["tipo"], mr._linea(c["defecto"], 300))]
        for i, r in enumerate(resultados[c["id"]], 1):
            if r["estado"] != "valida":
                partes.append("- Repetición %d: %s%s." % (
                    i, r["estado"], " (%s)" % r["detalle"] if r["detalle"] else ""))
                continue
            if not r["hallazgos"] and not r["pendientes"]:
                partes.append("- Repetición %d: sin hallazgos ni pendientes." % i)
            for h in r["hallazgos"]:
                partes.append("- Repetición %d, hallazgo %s [%s] en %s: %s" % (
                    i, h["severidad"], h["donde"], mr._codigo(h["archivo"], 120), h["problema"]))
            for p in r["pendientes"]:
                partes.append("- Repetición %d, pendiente [%s] en %s: %s" % (
                    i, p["donde"], mr._codigo(p["archivo"], 120), p["escenario"]))
    return "\n".join(partes) + "\n"


def listar(casos):
    """Casos y objetivos, sin llamar a la API: comprueba que los commits existen."""
    lineas = []
    for c in casos:
        diff = mr.obtener_diff(c["base"], c["cabeza"])
        lineas.append("%s [%s] diff=%d caracteres" % (c["id"], c["tipo"], len(diff)))
        for archivo, rangos in sorted(objetivos(c).items()):
            lineas.append("  %s%s" % (archivo, "".join(
                "\n    %d-%d %s" % r for r in rangos)))
        if c["tipo"] == "positivo" and not objetivos(c):
            lineas.append("  SIN OBJETIVO: el arreglo no toca código Python de la cabeza")
    return "\n".join(lineas)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--casos", default=CASOS)
    ap.add_argument("--solo", default="", help="ids separados por comas")
    ap.add_argument("--repeticiones", type=int, default=2)
    ap.add_argument("--salida", help="ruta del JSON con cada revisión")
    ap.add_argument("--ejecutar", action="store_true", help="llamar a la API de Mistral")
    args = ap.parse_args(argv)
    casos = cargar_casos(args.casos)
    if args.solo.strip():
        pedidos = {x.strip() for x in args.solo.split(",") if x.strip()}
        desconocidos = pedidos - {c["id"] for c in casos}
        if desconocidos:
            print("::error::Casos desconocidos: %s" % ", ".join(sorted(desconocidos)))
            return 2
        casos = [c for c in casos if c["id"] in pedidos]
    if not args.ejecutar:
        print(listar(casos))
        return 0
    if args.repeticiones < 1 or (
            len(casos) * args.repeticiones * mr.INTENTOS_RESPUESTA > MAX_LLAMADAS):
        print("::error::Hasta %d solicitudes por ejecución: reduce casos o repeticiones."
              % MAX_LLAMADAS)
        return 2
    clave = os.environ.get("MISTRAL_API_KEY", "")
    if not clave:
        print("::error::Falta MISTRAL_API_KEY: la evaluación no se ha ejecutado.")
        return 2
    modelo = os.environ.get("MISTRAL_MODEL") or "codestral-latest"
    resultados = {}
    for c in casos:
        resultados[c["id"]] = []
        for n in range(args.repeticiones):
            registro = revisar(c, modelo, clave)
            resultados[c["id"]].append(registro)
            print("%s repetición %d: %s, %d hallazgo(s)" % (
                c["id"], n + 1, registro["estado"], len(registro["hallazgos"])))
    informe = resumir(casos, resultados, modelo, args.repeticiones)
    mr.escribir_resumen(informe)
    print(informe)
    if args.salida:
        with open(args.salida, "w", encoding="utf-8") as fh:
            json.dump({"modelo": modelo, "repeticiones": args.repeticiones,
                       "casos": casos, "resultados": resultados},
                      fh, ensure_ascii=False, indent=2)
    return 0


if __name__ == "__main__":
    sys.exit(main())
