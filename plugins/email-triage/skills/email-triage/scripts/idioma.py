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

Uso (recomendado: el mensaje en bruto por stdin desde un FICHERO escrito con la
herramienta de escritura del agente; nunca por heredoc ni interpolado en la shell,
porque una línea igual al delimitador cerraría el heredoc y ejecutaría el resto):
  python3 idioma.py resolver --texto [--config-idioma fr] < ~/.email-triage/tmp/idioma_msg.txt
También acepta JSON: {"argumentos": "...", "config_idioma": "..."}. Si el JSON es
inválido devuelve `es` con un aviso `entrada_invalida` (nunca en silencio).
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
    r = sub.add_parser("resolver", help="stdin -> JSON por stdout")
    r.add_argument("--i18n", default=DIR_I18N)
    r.add_argument("--texto", action="store_true",
                   help="stdin es el mensaje del usuario en bruto (sin JSON); evita que las "
                        "comillas y apóstrofos del mensaje rompan el comando")
    r.add_argument("--config-idioma", default=None,
                   help="valor de usuario.idioma (solo con --texto)")
    args = ap.parse_args(sys.argv[1:] if argv is None else argv)
    entrada = sys.stdin.read()
    avisos_extra = []
    if args.texto:
        argumentos, config_idioma = entrada, args.config_idioma
    else:
        argumentos = config_idioma = None
        try:
            datos = json.loads(entrada or "{}")
            if not isinstance(datos, dict):
                raise ValueError("no es un objeto JSON")
            argumentos, config_idioma = datos.get("argumentos"), datos.get("config_idioma")
        except ValueError:
            # Un JSON roto NO puede degradar a `es` en silencio: se avisa para que el
            # skill aplique la regla a mano o use --texto.
            avisos_extra.append({"motivo": "entrada_invalida", "codigo": ""})
    salida = resolver(argumentos, config_idioma, args.i18n)
    salida["avisos"] = salida["avisos"] + avisos_extra
    print(json.dumps(salida, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
