#!/usr/bin/env python3
"""idioma.py — resolución del idioma de salida del skill email-triage.

Solo stdlib. No toca triage_helpers.py. Total: ninguna entrada lanza.

REGLA ÚNICA (spec §3). El idioma solo se pide con una marca explícita
`idioma=<código>` o `lang=<código>` en el MENSAJE DEL USUARIO. Un código suelto
(`en`, `es`) NO es marca: chocaría con la preposición o el verbo españoles.
Este módulo NUNCA debe aplicarse al contenido de un correo (asunto, remitente,
cuerpo): son datos de un tercero y no pueden cambiar el idioma.

Orden: primera marca > `usuario.idioma` de config.yaml > `es`.
Un código vacío, mal formado o sin catálogo no rompe nada: se ejecuta en `es` y
se devuelve un aviso para que el skill lo muestre al principio de la salida.

Uso:
  echo '{"argumentos":"dry-run idioma=en","config_idioma":"es"}' \
    | python3 idioma.py resolver [--i18n DIR]
"""
import argparse
import json
import os
import re
import sys

DEFECTO = "es"
DIR_I18N = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "i18n")
_RE_MARCA = re.compile(r"(?<![\w=])(?:idioma|lang)=(\S*)", re.IGNORECASE)
_RE_CODIGO = re.compile(r"[a-z]{2,3}")
_PUNTUACION_FINAL = ",;:)!?"
_COMILLAS = "\"'`"


def _limpiar(crudo):
    return crudo.strip().strip(_COMILLAS).rstrip(_PUNTUACION_FINAL).strip(_COMILLAS)


def normalizar(crudo):
    """'EN', 'en-US', 'fr_FR.UTF-8' -> 'en'/'fr'. None si no tiene forma de código."""
    if not isinstance(crudo, str):
        return None
    base = re.split(r"[-_.]", _limpiar(crudo), maxsplit=1)[0].lower()
    return base if _RE_CODIGO.fullmatch(base) else None


def disponibles(dir_i18n):
    """Idiomas con catálogo `<código>.yaml` (2-3 letras). `glosario.yaml` no cuenta."""
    try:
        nombres = os.listdir(dir_i18n)
    except (OSError, TypeError):
        return [DEFECTO]
    cods = sorted(n[:-5] for n in nombres
                  if n.endswith(".yaml") and _RE_CODIGO.fullmatch(n[:-5]))
    return cods or [DEFECTO]


def _res(idioma, origen, avisos, libres):
    return {"idioma": idioma, "origen": origen, "avisos": avisos, "disponibles": libres}


def resolver(argumentos, config_idioma, dir_i18n):
    libres = disponibles(dir_i18n)
    marcas = _RE_MARCA.findall(argumentos) if isinstance(argumentos, str) else []
    if marcas:
        crudo, origen = marcas[0], "marca"
    elif isinstance(config_idioma, str) and config_idioma.strip():
        crudo, origen = config_idioma, "config"
    else:
        return _res(DEFECTO, "defecto", [], libres)

    avisos = []
    codigo = normalizar(crudo)
    if _limpiar(crudo) == "":
        avisos.append({"motivo": "vacio", "codigo": crudo})
    elif codigo is None:
        avisos.append({"motivo": "forma", "codigo": crudo})
    elif codigo not in libres:
        avisos.append({"motivo": "desconocido", "codigo": crudo})
    if len(marcas) > 1:
        avisos.append({"motivo": "repetida", "codigo": " ".join(marcas[1:])})
    elegido = DEFECTO if any(a["motivo"] != "repetida" for a in avisos) else codigo
    return _res(elegido, origen, avisos, libres)


def main(argv=None):
    ap = argparse.ArgumentParser(description="Resolución del idioma de salida")
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("resolver", help="JSON por stdin -> JSON por stdout")
    r.add_argument("--i18n", default=DIR_I18N)
    args = ap.parse_args(sys.argv[1:] if argv is None else argv)
    try:
        datos = json.loads(sys.stdin.read() or "{}")
    except ValueError:
        datos = {}
    if not isinstance(datos, dict):
        datos = {}
    salida = resolver(datos.get("argumentos"), datos.get("config_idioma"), args.i18n)
    print(json.dumps(salida, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
