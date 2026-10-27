#!/usr/bin/env python3
"""Evaluación opt-in con la API oficial de TypeSafe; nunca mueve ni escribe.

`preparar` sanitiza sin red. `comparar`/`evaluar` requieren opt-in y TYPESAFE_API_KEY.
Contrato contrastado el 2026-10-16: https://docs.typesafe.ai/api y /models.
Solo Choice: los valores se agregan con el scoring existente, sin inventar
explicaciones textuales que Jev no devuelve. Datos por stdin, no por la shell.
"""
import argparse
import json
from pathlib import Path
import re
import sys
import urllib.request  # noqa: F401 — los tests parchean j.urllib.request

import clasificadores as nc
import triage_helpers as th
# Reexportados: lo neutro vive en clasificadores.py (v3.22); estos nombres
# siguen accesibles como jev.X para tests y llamadores existentes.
from clasificadores import (  # noqa: F401
    INCIERTO, NO_APLICA, MAX_JSON, MAX_PETICION, _exigir, _numero, _texto,
    _objeto, _cargar_json, _json, _huella, _filas, preparar, _opciones,
    _validar_control, _principal, _scoring, _estado, _SinRedireccion)

ENDPOINT = "https://api.typesafe.ai/v1/systemone"
ALIASES = {"jev-latest", "jev-preview"}
PRECIOS_MTOK = {"jev-1.13.0": 0.042, "jev-1.14.0": 0.042}  # USD, tarifa publicada de ambos modelos a 2026-10-16.
DEFAULT = {"activo": False, "acepta_envio_datos": False, "modo": "comparar",
           "modelo": "jev-latest", "max_llamadas": 5,
           "timeout_segundos": 15, "confianza_minima": 0.8,
           "tolerancia_dudas": 0}

ErrorJev = nc.ErrorClasificador  # mismo tipo: los except existentes siguen valiendo


def _preguntas(cfg, activos):
    """Serialización Jev: Choice con `criteria` {valor: descripción|None}."""
    return {k: {"type": "choice", "criteria": q["opciones"], "instructions": q["instrucciones"]}
            for k, q in nc.preguntas_neutras(cfg, activos).items()}


def _version_jev(modelo):
    return isinstance(modelo, str) and re.fullmatch(r"jev-[0-9]{1,6}\.[0-9]{1,6}\.[0-9]{1,6}", modelo) is not None


def _modelo_efectivo(respuesta, solicitado):
    efectivo = respuesta.get("model") if isinstance(respuesta, dict) else None
    _exigir(_version_jev(efectivo) and (solicitado in ALIASES or efectivo == solicitado),
            "modelo_inesperado")
    return efectivo


def a_forma_interna(r, preguntas):
    """Jev ya usa la forma interna: `answers` es un dict por criterio."""
    answers = r.get("answers")
    _exigir(isinstance(answers, dict) and set(answers) == set(preguntas), "cobertura_jev")
    return answers


def validar_respuesta(r, preguntas, modelo):
    _modelo_efectivo(r, modelo)
    answers = a_forma_interna(r, preguntas)
    return nc.validar_forma(answers, {k: q["criteria"] for k, q in preguntas.items()}, "jev")


def solicitar(body, key, timeout):
    """Destino fijo HTTPS; TLS y proxy del entorno; sin redirect ni reintentos."""
    return nc.solicitar(ENDPOINT, body, key, timeout)


def _config(capa):
    return nc.config_capa(capa, DEFAULT, lambda m: isinstance(m, str)
                          and (m in ALIASES or _version_jev(m)), "jev")


def _cuerpo(modelo, perfil, estado, preguntas):
    return {"model": modelo, "state": {"perfil_minimo": perfil, "correo": estado},
            "questions": preguntas}


PROVEEDOR = nc.Proveedor(
    nombre="typesafe", etiqueta="jev", variable_clave="TYPESAFE_API_KEY",
    tarifas=PRECIOS_MTOK, tarifa_fecha="2026-10-16",
    config=lambda capa: _config(capa), preguntas=_preguntas, cuerpo=_cuerpo,
    modelo_efectivo=lambda r, s: _modelo_efectivo(r, s),
    uso=lambda r: nc.uso_tokens(r.get("usage"), ("input_tokens", "output_tokens")),
    validar=lambda r, q, m: validar_respuesta(r, q, m),
    # Resolución tardía: un patch de jev.solicitar sigue surtiendo efecto.
    transporte=lambda body, key, timeout: solicitar(body, key, timeout))


def comparar(p, cfg, capa, transporte=None):
    return nc.procesar(p, cfg, capa, transporte, "comparar", PROVEEDOR)


def evaluar(p, cfg, capa, transporte=None):
    """Veredictos para el flujo real; revisión y autorización siguen en el principal."""
    return nc.procesar(p, cfg, capa, transporte, "hibrido", PROVEEDOR)


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
        comp.add_argument("--config-ensayo")  # v3.21.31, como scoring
        comp.add_argument("--config-jev", default=str(Path(th.base_estado()) / "config-jev.yaml"))
    args = parser.parse_args()
    try:
        raw = sys.stdin.buffer.read(MAX_JSON + 1)
        _exigir(len(raw) <= MAX_JSON, "entrada_excesiva")
        p = _cargar_json(raw.decode("utf-8"))
        if args.cmd == "preparar":
            out = preparar(p)
        else:
            capa = _yaml(args.config_jev, opcional=True)
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
