#!/usr/bin/env python3
"""Evaluación opt-in con la API Decisions de OpenAI; nunca mueve ni escribe.

`preparar` sanitiza sin red. `comparar`/`evaluar` requieren opt-in y OPENAI_API_KEY.
Contrato contrastado el 2026-10-25: https://developers.openai.com/api/docs/guides/decisions
y /api/reference/resources/decisions/methods/create. Adaptador fino sobre
`clasificadores.py`: aquí solo se serializa la petición, se convierte la
respuesta a la forma interna común y se fijan endpoint, modelo y tarifa.
Solo preguntas Choice; datos por stdin, no por la shell.
"""
import argparse
import json
from pathlib import Path
import re
import sys

import clasificadores as nc
import triage_helpers as th
from clasificadores import _exigir, preparar, MAX_JSON  # noqa: F401

ENDPOINT = "https://api.openai.com/v1/decisions"
MODELO_POR_DEFECTO = "gpt-6-luna"  # único admitido por /v1/decisions a 2026-10-25
# USD por millón de tokens de entrada sin caché; salida sin coste. Consulta 2026-10-25.
# La caché se desactiva en cada petición (ver `_cuerpo`), así que todo el input
# se cobra a esta tarifa. No recoge recargos regionales (+10 %) ni de contexto
# largo: la cifra es una estimación que puede quedarse corta, no una cota.
PRECIOS_MTOK = {"gpt-6-luna": 0.10}
TARIFA_FECHA = "2026-10-25"
DEFAULT = {"activo": False, "acepta_envio_datos": False, "modo": "comparar",
           "modelo": MODELO_POR_DEFECTO, "max_llamadas": 5,
           "timeout_segundos": 15, "confianza_minima": 0.8}

ErrorDecisions = nc.ErrorClasificador


def _modelo_valido(modelo):
    """`gpt-6-luna` por defecto; otro ID solo si la persona lo escribe en su capa.

    Sin alias: el modelo efectivo debe coincidir exactamente con el solicitado.
    """
    return isinstance(modelo, str) and re.fullmatch(r"gpt-[a-z0-9][a-z0-9.\-]{0,62}", modelo) is not None


def _preguntas(cfg, activos):
    """Serialización Decisions: lista de Choice con `name` único y `choices`."""
    preguntas = []
    for k, q in nc.preguntas_neutras(cfg, activos).items():
        choices = []
        for valor, descripcion in q["opciones"].items():
            op = {"value": valor}
            if descripcion is not None:
                op["description"] = descripcion
            choices.append(op)
        preguntas.append({"type": "choice", "name": k,
                          "instructions": q["instrucciones"], "choices": choices})
    return preguntas


def _opciones_por_criterio(preguntas):
    return {q["name"]: {c["value"] for c in q["choices"]} for q in preguntas}


def _cuerpo(modelo, perfil, estado, preguntas):
    # Entrada compartida en texto: sin imágenes, input_json ni historial.
    entrada = json.dumps({"perfil_minimo": perfil, "correo": estado},
                         ensure_ascii=False, sort_keys=True)
    # Modo explícito sin breakpoints = sin caché (referencia de create): sin
    # escrituras de caché más caras ni extractos retenidos en la caché.
    return {"model": modelo, "input": entrada, "questions": preguntas,
            "prompt_cache_options": {"mode": "explicit"}}


def _uso(respuesta):
    """Tokens observados; si la API informa caché pese a desactivarla, coste desconocido."""
    usage = respuesta.get("usage")
    tokens = nc.uso_tokens(usage, ("input_tokens", "output_tokens"))
    detalles = usage.get("input_tokens_details") if isinstance(usage, dict) else None
    if tokens is None or detalles is None:
        return tokens
    if not (isinstance(detalles, dict) and all(
            detalles.get(k, 0) == 0 and type(detalles.get(k, 0)) is int
            for k in ("cached_tokens", "cache_write_tokens"))):
        return None
    return tokens


def _modelo_efectivo(respuesta, solicitado):
    efectivo = respuesta.get("model") if isinstance(respuesta, dict) else None
    _exigir(_modelo_valido(efectivo) and efectivo == solicitado, "modelo_inesperado")
    return efectivo


def a_forma_interna(r, preguntas):
    """Lista `answers` de Decisions → dict por criterio de la forma interna común.

    Un `refusal` en cualquier pregunta es abstención del correo entero: no se
    puntúa con criterios ausentes. Se rechazan nombres nulos o duplicados,
    valores booleanos y probabilidades repetidas.
    """
    answers = r.get("answers")
    _exigir(isinstance(answers, list), "cobertura_decisions")
    _exigir(not any(isinstance(a, dict) and a.get("type") == "refusal" for a in answers),
            "decisions_refusal")
    nombres = {q["name"] for q in preguntas}
    forma = {}
    for a in answers:
        _exigir(isinstance(a, dict) and isinstance(a.get("name"), str)
                and a["name"] in nombres and a["name"] not in forma, "cobertura_decisions")
        _exigir(a.get("type") == "choice"
                and set(a) == {"type", "name", "choice", "probabilities", "confidence"},
                "tipo_respuesta")
        ps = a["probabilities"]
        _exigir(isinstance(ps, list), "probabilidades_invalidas")
        dist = {}
        for item in ps:
            _exigir(nc._objeto(item, ("value", "probability"))
                    and type(item["value"]) is str and item["value"] not in dist,
                    "probabilidades_invalidas")
            dist[item["value"]] = item["probability"]
        _exigir(type(a["choice"]) is str, "opcion_decisions_invalida")
        forma[a["name"]] = {"type": "choice", "choice": a["choice"],
                            "probabilities": dist, "confidence": a["confidence"]}
    _exigir(set(forma) == nombres, "cobertura_decisions")
    return forma


def validar_respuesta(r, preguntas, modelo):
    _modelo_efectivo(r, modelo)
    forma = a_forma_interna(r, preguntas)
    return nc.validar_forma(forma, _opciones_por_criterio(preguntas), "decisions")


def solicitar(body, key, timeout):
    """Destino fijo HTTPS; TLS y proxy del entorno; sin redirect ni reintentos."""
    return nc.solicitar(ENDPOINT, body, key, timeout)


def _config(capa):
    return nc.config_capa(capa, DEFAULT, _modelo_valido, "decisions")


PROVEEDOR = nc.Proveedor(
    nombre="openai_decisions", etiqueta="decisions", variable_clave="OPENAI_API_KEY",
    tarifas=PRECIOS_MTOK, tarifa_fecha=TARIFA_FECHA,
    config=lambda capa: _config(capa), preguntas=_preguntas, cuerpo=_cuerpo,
    modelo_efectivo=lambda r, s: _modelo_efectivo(r, s),
    uso=lambda r: _uso(r),
    validar=lambda r, q, m: validar_respuesta(r, q, m),
    # Resolución tardía: un patch de decisions.solicitar sigue surtiendo efecto.
    transporte=lambda body, key, timeout: solicitar(body, key, timeout))


def _anotar(salida):
    salida["consumo"]["coste_excluye_recargos"] = True  # regional y contexto largo
    return salida


def comparar(p, cfg, capa, transporte=None):
    return _anotar(nc.procesar(p, cfg, capa, transporte, "comparar", PROVEEDOR))


def evaluar(p, cfg, capa, transporte=None):
    """Veredictos para el flujo real; revisión y autorización siguen en el principal."""
    return _anotar(nc.procesar(p, cfg, capa, transporte, "hibrido", PROVEEDOR))


def _yaml(ruta, opcional=False):
    p = Path(ruta).expanduser()
    if opcional and not p.exists():
        return {}
    import yaml
    with p.open(encoding="utf-8") as f:
        r = yaml.safe_load(f)
    _exigir(isinstance(r, dict), "config_invalida")
    return r


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("preparar")
    for nombre in ("comparar", "evaluar"):
        comp = sub.add_parser(nombre)
        comp.add_argument("--config", required=True)
        comp.add_argument("--config-veloz")
        comp.add_argument("--config-ensayo")
        comp.add_argument("--config-decisions",
                          default=str(Path(th.base_estado()) / "config-decisions.yaml"))
    args = parser.parse_args()
    try:
        raw = sys.stdin.buffer.read(MAX_JSON + 1)
        _exigir(len(raw) <= MAX_JSON, "entrada_excesiva")
        p = nc._cargar_json(raw.decode("utf-8"))
        if args.cmd == "preparar":
            out = preparar(p)
        else:
            capa = _yaml(args.config_decisions, opcional=True)
            c = _config(capa)
            cfg = _yaml(args.config) if c["activo"] else {}
            if c["activo"] and args.config_veloz:
                cfg = th._merge_config(cfg, _yaml(args.config_veloz))
            if c["activo"]:
                cfg = th._fusiona_config_ensayo(cfg, args.config_ensayo)
            out = (evaluar if args.cmd == "evaluar" else comparar)(p, cfg, capa)
    except Exception:
        # Fallos de fichero/YAML/JSON: no imprimir paths, entrada o credencial.
        out = {"ok": False, "motivo": "entrada_o_config_invalida",
               "usar_principal": True, "permitir_movimientos": False,
               "requiere_simulacion": True}
    print(json.dumps(out, ensure_ascii=False, allow_nan=False))
    return 0 if out.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
