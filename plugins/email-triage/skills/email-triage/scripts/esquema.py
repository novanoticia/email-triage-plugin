#!/usr/bin/env python3
"""Esquema JSON portable de la respuesta del evaluador nativo.

No invoca modelos, no accede a red/buzón y no escribe archivos. Rutas por
argumentos, datos por stdin, salida por stdout, sin contenido de correos en
los errores (mismas garantías que `modelos.py`).

El esquema es un artefacto de CONTRATO, no una integración: un host que sepa
pedir salida estructurada puede usarlo; uno que no, sigue igual que antes.
Usa solo el subconjunto común de los Structured Outputs de Anthropic, OpenAI
(`strict`), Gemini y Mistral: todas las propiedades en `required`,
`additionalProperties: false` y lo opcional como tipo anulable.

Ese modo estricto obliga a que TODAS las claves estén presentes (con `null`
donde no aplica), y `modelos._validar_fila` decide por presencia de claves.
`normalizar` traduce de una forma a otra quitando los `null`; no rellena,
no corrige ni infiere. Lo que el esquema no puede garantizar (exactamente
una opción por criterio, evidencia cuando hay veredicto, `no_aplica` solo en
no core, `eco` igual al ancla) lo sigue comprobando `modelos.validar`.
"""
import argparse
import json
import sys

import modelos
import triage_helpers as th


# Subconjunto permitido; el test lo recorre contra estas mismas listas.
_PALABRAS = {"type", "properties", "required", "additionalProperties",
             "enum", "items", "description"}
_TIPOS = {"object", "array", "string", "boolean", "null"}
_POR_CRITERIO = ("verdicts", "no_aplica", "evidencias")


def _objeto(propiedades, descripcion=None):
    o = {"type": "object", "properties": propiedades,
         "required": list(propiedades), "additionalProperties": False}
    if descripcion:
        o["description"] = descripcion
    return o


def generar(cfg):
    """Esquema desde los criterios activos de la configuración YA fusionada.

    Los ids salen de `modelos._criterios` (sin lista paralela); el orden de
    criterios y opciones es el del config, para que el esquema sea legible.
    """
    activos = modelos._criterios(cfg)
    crit = cfg["criterios_epistemicos"]
    vs, na, ev = {}, {}, {}
    for k in crit:
        if k not in activos:
            continue
        opciones, core = activos[k]
        pregunta = crit[k].get("question")
        desc = pregunta if isinstance(pregunta, str) else k
        orden = [o for o in crit[k] if o in opciones]
        vs[k] = {"type": ["string", "null"], "enum": orden + [None],
                 "description": desc}
        # Core: el esquema ya impide excluirlo; la razón siempre es null.
        na[k] = ({"type": "null", "description": desc + " (core: no se excluye)"}
                 if core else {"type": ["string", "null"], "description": desc})
        ev[k] = {"type": ["string", "null"], "description": desc}
    fila = _objeto({
        "id": {"type": "string"},
        "verdicts": _objeto(vs, "Una opción por criterio, o null si va en no_aplica."),
        "no_aplica": _objeto(na, "Razón de exclusión (solo no core), o null."),
        "evidencias": _objeto(ev, "Evidencia de cada veredicto, o null si no hay veredicto."),
        "dudas": {"type": "array", "items": {"type": "string"}},
        "resumen": {"type": "string"},
        # Objeto NO anulable: un objeto con `type: [object, null]` no lo
        # aceptan todos los modos estrictos (revisión PR #135). Sin ancla,
        # `validar` ignora el eco; con ancla, uno vacío da `eco_distinto`.
        "eco": _objeto({"inicio": {"type": "string"}, "fin": {"type": "string"}},
                       "Inicio y fin del texto recibido; cadenas vacías si no se pidió."),
    })
    return _objeto({"evaluaciones": {"type": "array", "items": fila}})


def normalizar(respuesta):
    """Forma «esquema» → forma «validador». Pura y determinista.

    Quita las entradas None de verdicts/no_aplica/evidencias y elimina `eco`
    si vale None (respuestas que no usan el esquema). No toca ningún otro valor. Devuelve
    {"ok": True, "respuesta": {...}} o `modelos._error(motivo)`.
    """
    if not isinstance(respuesta, dict) or not isinstance(
            respuesta.get("evaluaciones"), list):
        return modelos._error("respuesta_invalida")
    filas = []
    for fila in respuesta["evaluaciones"]:
        if not isinstance(fila, dict):
            return modelos._error("fila_invalida")
        nueva = {}
        for k, v in fila.items():
            if k in _POR_CRITERIO:
                if not isinstance(v, dict):
                    return modelos._error("veredictos_invalidos")
                v = {c: x for c, x in v.items() if x is not None}
            elif k == "eco" and v is None:
                continue
            nueva[k] = v
        filas.append(nueva)
    otros = {k: v for k, v in respuesta.items() if k != "evaluaciones"}
    return {"ok": True, "respuesta": dict(otros, evaluaciones=filas)}


def _tipo_ok(valor, tipo):
    if tipo == "null":
        return valor is None
    if tipo == "boolean":
        return type(valor) is bool
    if tipo == "string":
        return isinstance(valor, str)
    if tipo == "array":
        return isinstance(valor, list)
    return isinstance(valor, dict)


def errores(valor, esquema, ruta="$"):
    """Comprobador mínimo del subconjunto (tipos, enum, required,
    additionalProperties, items). Las rutas nombran claves, nunca valores."""
    tipos = esquema.get("type")
    tipos = tipos if isinstance(tipos, list) else [tipos]
    if not any(_tipo_ok(valor, t) for t in tipos):
        return [ruta + ": tipo"]
    if "enum" in esquema and valor not in esquema["enum"]:
        return [ruta + ": enum"]
    out = []
    if isinstance(valor, dict) and "properties" in esquema:
        props = esquema["properties"]
        out += [ruta + "." + k + ": requerido"
                for k in esquema.get("required", []) if k not in valor]
        if esquema.get("additionalProperties") is False:
            out += [ruta + ": clave_no_permitida" for k in valor if k not in props]
        for k, sub in props.items():
            if k in valor:
                out += errores(valor[k], sub, ruta + "." + k)
    if isinstance(valor, list) and "items" in esquema:
        for i, x in enumerate(valor):
            out += errores(x, esquema["items"], "%s[%d]" % (ruta, i))
    return out


def comprobar(cfg, respuesta):
    """Conformidad con el esquema + normalización. NO llama a `validar`:
    eso lo hace el orquestador con el plan de `planificar`."""
    errs = errores(respuesta, generar(cfg))
    norm = normalizar(respuesta)
    if not norm["ok"]:
        return dict(norm, conforme=False, errores=errs)
    return {"ok": True, "conforme": not errs, "errores": errs,
            "normalizada": norm["respuesta"]}


def _config(args):
    if (args.config_veloz or args.config_ensayo) and not args.config:
        raise ValueError("config_base_requerida")
    # Misma carga/fusión que `modelos.main` para `validar`.
    return th._fusiona_config_ensayo(
        th._fusiona_config_veloz(th._cargar_config(args.config),
                                 args.config_veloz),
        args.config_ensayo)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="comando", required=True)
    for nombre in ("generar", "comprobar"):
        p = sub.add_parser(nombre)
        p.add_argument("--config", required=True, help="Config YAML canónico")
        p.add_argument("--config-veloz", help="Capa veloz, solo con --config")
        p.add_argument("--config-ensayo", help="Capa del ensayo P3, solo con --config")
    sub.add_parser("normalizar")
    args = parser.parse_args()
    try:
        if args.comando == "generar":
            salida = generar(_config(args))
            print(json.dumps(salida, ensure_ascii=False, indent=2))
            return 0
        entrada = json.load(sys.stdin)
        salida = (normalizar(entrada) if args.comando == "normalizar"
                  else comprobar(_config(args), entrada))
    except (ValueError, TypeError, KeyError, UnicodeError, OSError,
            th.ConfigError, SystemExit, RecursionError):
        salida = modelos._error("entrada_o_config_invalida")
    print(json.dumps(salida, ensure_ascii=False, allow_nan=False))
    return 0 if salida.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
