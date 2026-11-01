#!/usr/bin/env python3
"""Modelos de decisión locales de Ollama (`/v1/systemone`); nunca mueve ni escribe.

Cuarto adaptador de decisión, junto a Jev, OpenAI Decisions y OpenRouter, y
el único en el que el correo no sale del Mac: solo habla con
`http://127.0.0.1:11434`, sin clave y sin proxy (`nc.solicitar` con
`key=None`). Contrato comprobado en un Mac de 16 GB el 2026-11-01
(`scripts/sonda_ollama.py` y `scripts/sonda_decision_local.py`, Ollama
0.40.13, correos ficticios): `/v1/systemone` recibe y devuelve exactamente la
forma de Jev (`state` + `questions` Choice → `answers` con `choice`,
`probabilities` y `confidence`, más `model` igual al pedido y `usage`).

**Lo que dicen las mediciones** (12 correos ficticios, 3 variantes de las
preguntas): ninguna fila pasa el freno de `hibrido` (0 inciertos y
confianza >= 0,8 en los 30 criterios). `d1` responde en 3-4 s con confianza
mediana 0,46; `tev1:4b`, en 12-16 s con 0,11. Sirve para `comparar` en local
(sin coste y sin enviar nada fuera); en `hibrido` cada fila vuelve al
principal, como debe. El freno no se relaja para él.

Lo neutro (preguntas, validación, frenos) vive en `clasificadores.py`; aquí
solo se fijan endpoint, modelos y la comprobación del modelo efectivo.
"""
import argparse
import json
from pathlib import Path
import sys

import clasificadores as nc
import triage_helpers as th
from clasificadores import _exigir, _cargar_json, preparar, MAX_JSON  # noqa: F401

PUERTO = 11434
ENDPOINT = nc.LOOPBACK + "%d/v1/systemone" % PUERTO
MODELO_POR_DEFECTO = "d1:latest"  # el más rápido y con más confianza en la sonda
MODELOS = (MODELO_POR_DEFECTO, "tev1:4b")  # solo los sondeados
DEFAULT = {"activo": False, "acepta_envio_datos": False, "modo": "comparar",
           "modelo": MODELO_POR_DEFECTO, "max_llamadas": 5,
           "timeout_segundos": 60, "confianza_minima": 0.8,
           "tolerancia_dudas": 0}
ErrorDecisionLocal = nc.ErrorClasificador


def _preguntas(cfg, activos):
    """Misma serialización que Jev: el contrato de `/v1/systemone` es idéntico."""
    return {k: {"type": "choice", "criteria": q["opciones"], "instructions": q["instrucciones"]}
            for k, q in nc.preguntas_neutras(cfg, activos).items()}


def _cuerpo(modelo, perfil, estado, preguntas):
    return {"model": modelo, "state": {"perfil_minimo": perfil, "correo": estado},
            "questions": preguntas}


def _modelo_efectivo(respuesta, solicitado):
    efectivo = respuesta.get("model") if isinstance(respuesta, dict) else None
    _exigir(efectivo == solicitado, "modelo_inesperado")
    return efectivo


def validar_respuesta(r, preguntas, modelo):
    _modelo_efectivo(r, modelo)
    answers = r.get("answers")
    _exigir(isinstance(answers, dict) and set(answers) == set(preguntas), "cobertura_decision_local")
    return nc.validar_forma(answers, {k: q["criteria"] for k, q in preguntas.items()}, "decision_local")


def solicitar(body, key, timeout):
    """Solo loopback, sin clave ni proxy; la clave que llegue se ignora."""
    return nc.solicitar(ENDPOINT, body, None, timeout)


def _config(capa):
    return nc.config_capa(capa, DEFAULT, lambda m: m in MODELOS, "decision_local")


PROVEEDOR = nc.Proveedor(
    nombre="ollama_decision", etiqueta="decision_local", variable_clave=None,
    tarifas={m: 0.0 for m in MODELOS}, tarifa_fecha="2026-11-01",  # sin facturación
    config=_config, preguntas=_preguntas, cuerpo=_cuerpo,
    modelo_efectivo=_modelo_efectivo,
    uso=lambda r: nc.uso_tokens(r.get("usage"), ("input_tokens", "output_tokens")),
    validar=validar_respuesta,
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
    canonica = str(Path(th.base_estado()) / "config-decision-local.yaml")
    for nombre in ("comparar", "evaluar"):
        comp = sub.add_parser(nombre)
        comp.add_argument("--config", required=True)
        comp.add_argument("--config-veloz")
        comp.add_argument("--config-ensayo")
        comp.add_argument("--config-decision-local", default=canonica)
    args = parser.parse_args()
    try:
        raw = sys.stdin.buffer.read(MAX_JSON + 1)
        _exigir(len(raw) <= MAX_JSON, "entrada_excesiva")
        p = _cargar_json(raw.decode("utf-8"))
        if args.cmd == "preparar":
            out = preparar(p)
        else:
            capa = nc.capa_desde_disco(args.config_decision_local, canonica, _yaml, _config)
            c = _config(capa)
            cfg = _yaml(args.config) if c["activo"] else {}
            if c["activo"] and args.config_veloz:
                cfg = th._merge_config(cfg, _yaml(args.config_veloz))
            if c["activo"]:
                cfg = th._fusiona_config_ensayo(cfg, args.config_ensayo)
            out = (evaluar if args.cmd == "evaluar" else comparar)(p, cfg, capa)
    except nc.ErrorCapaDisco as exc:
        out = {"ok": False, "motivo": str(exc), "usar_principal": True,
               "permitir_movimientos": False, "requiere_simulacion": True}
    except Exception:
        # Fallos de fichero/YAML/JSON: no imprimir paths ni entrada.
        out = {"ok": False, "motivo": "entrada_o_config_invalida",
               "usar_principal": True, "permitir_movimientos": False,
               "requiere_simulacion": True}
    print(json.dumps(out, ensure_ascii=False, allow_nan=False))
    return 0 if out.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
