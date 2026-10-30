#!/usr/bin/env python3
"""Decisiones opt-in mediante OpenRouter; sin movimientos ni escrituras.

Contrato Choice de https://openrouter.ai/blog/insights/what-is-jev/
consultado el 2026-10-30. Solo modelos compatibles con Decisions, no chat.
"""
import argparse
from pathlib import Path
import json
import re
import sys

import clasificadores as nc
import triage_helpers as th
from clasificadores import _exigir, _cargar_json, preparar, MAX_JSON

ENDPOINT = "https://openrouter.ai/api/alpha/decisions"
MODELO_POR_DEFECTO = "microsoft/microsoft-decision-1"
DEFAULT = {"activo": False, "acepta_envio_datos": False, "modo": "comparar",
           "modelo": MODELO_POR_DEFECTO, "max_llamadas": 5,
           "timeout_segundos": 15, "confianza_minima": 0.8,
           "tolerancia_dudas": 0}
ErrorOpenRouter = nc.ErrorClasificador


def _modelo_valido(modelo):
    # ID completo del catálogo, sin URLs, rutas relativas ni selector automático.
    return (isinstance(modelo, str) and len(modelo) <= 200
            and re.fullmatch(r"[a-z0-9][a-z0-9_-]*/[a-z0-9][a-z0-9._:+-]*", modelo) is not None
            and ".." not in modelo and modelo != "openrouter/auto")


def _modelo_efectivo(respuesta, solicitado):
    efectivo = respuesta.get("model") if isinstance(respuesta, dict) else None
    # OpenRouter puede resolver el ID a un snapshot con fecha YYYYMMDD.
    _exigir(_modelo_valido(efectivo) and
            (efectivo == solicitado or re.fullmatch(re.escape(solicitado) + r"-[0-9]{8}", efectivo)),
            "modelo_inesperado")
    return efectivo


def _preguntas(cfg, activos):
    return {k: {"type": "choice", "criteria": q["opciones"], "instructions": q["instrucciones"]}
            for k, q in nc.preguntas_neutras(cfg, activos).items()}


def _cuerpo(modelo, perfil, estado, preguntas):
    return {"model": modelo, "state": {"perfil_minimo": perfil, "correo": estado},
            "questions": preguntas}


def validar_respuesta(r, preguntas, modelo):
    _modelo_efectivo(r, modelo)
    answers = r.get("answers")
    _exigir(isinstance(answers, dict) and set(answers) == set(preguntas), "cobertura_openrouter")
    return nc.validar_forma(answers, {k: q["criteria"] for k, q in preguntas.items()}, "openrouter")


def solicitar(body, key, timeout):
    return nc.solicitar(ENDPOINT, body, key, timeout)


def _config(capa):
    return nc.config_capa(capa, DEFAULT, _modelo_valido, "openrouter")


PROVEEDOR = nc.Proveedor(
    nombre="openrouter", etiqueta="openrouter", variable_clave="OPENROUTER_API_KEY",
    # Los modelos son intercambiables: no extrapolar precios entre ellos.
    tarifas={}, tarifa_fecha=None,
    config=_config, preguntas=_preguntas, cuerpo=_cuerpo,
    modelo_efectivo=_modelo_efectivo,
    uso=lambda r: nc.uso_tokens(r.get("usage"), ("input_tokens", "output_tokens")),
    validar=validar_respuesta,
    transporte=lambda body, key, timeout: solicitar(body, key, timeout))


def _diagnosticar(salida):
    """Añade códigos de ayuda seguros; el orquestador los explica en su idioma.

    Conserva `motivo`. Nunca lee mensajes/cuerpos HTTP ni deduce la causa de
    un 400/404, que pueden tener varios significados.
    """
    categorias = {
        "credencial_ausente_o_invalida": "credencial_local",
        "http_401": "autenticacion", "http_402": "saldo_o_credito",
        "http_403": "acceso_denegado",
        "http_400": "peticion_o_modelo", "http_404": "recurso_o_modelo",
        "http_422": "peticion_o_capacidades", "http_429": "limite_solicitudes",
        "fallo_red_o_timeout": "conexion_o_timeout",
        "modelo_no_verificado": "identificador_modelo_invalido",
        "modelo_inesperado": "modelo_distinto",
        "proveedor_detenido": "llamadas_suspendidas",
    }
    invalidas = {"cobertura_openrouter", "tipo_respuesta", "probabilidades_invalidas",
                 "opcion_no_maxima", "opcion_openrouter_invalida", "confianza_invalida",
                 "usage_invalido", "respuesta_json_invalida", "respuesta_excesiva",
                 "respuesta_http_inesperada", "redireccion_rechazada"}
    for fila in [salida] + salida.get("resultados", []):
        motivo = fila.get("motivo", "")
        categoria = categorias.get(motivo)
        if motivo in invalidas:
            categoria = "respuesta_invalida_o_incompatible"
        if re.fullmatch(r"http_5[0-9]{2}", motivo):
            categoria = "fallo_servicio"
        if categoria:
            fila["diagnostico_error"] = categoria
    return salida


def comparar(p, cfg, capa, transporte=None):
    return _diagnosticar(nc.procesar(p, cfg, capa, transporte, "comparar", PROVEEDOR))


def evaluar(p, cfg, capa, transporte=None):
    return _diagnosticar(nc.procesar(p, cfg, capa, transporte, "hibrido", PROVEEDOR))


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
        comp.add_argument("--config-openrouter", default=str(Path(th.base_estado()) / "config-openrouter.yaml"))
    args = parser.parse_args()
    try:
        raw = sys.stdin.buffer.read(MAX_JSON + 1)
        _exigir(len(raw) <= MAX_JSON, "entrada_excesiva")
        p = _cargar_json(raw.decode("utf-8"))
        if args.cmd == "preparar":
            out = preparar(p)
        else:
            capa = nc.capa_desde_disco(args.config_openrouter,
                                       str(Path(th.base_estado()) / "config-openrouter.yaml"), _yaml, _config)
            c = _config(capa)
            cfg = _yaml(args.config) if c["activo"] else {}
            if c["activo"] and args.config_veloz:
                cfg = th._merge_config(cfg, _yaml(args.config_veloz))
            if c["activo"]:
                cfg = th._fusiona_config_ensayo(cfg, args.config_ensayo)
            out = (evaluar if args.cmd == "evaluar" else comparar)(p, cfg, capa)
    except nc.ErrorCapaDisco as exc:
        # v3.22.23: el config no es el de la base ni se ajusta a él; el código
        # dice cuál (sin rutas ni contenido).
        out = {"ok": False, "motivo": str(exc), "usar_principal": True,
               "permitir_movimientos": False, "requiere_simulacion": True}
    except Exception:
        # Fallos de fichero/YAML/JSON: no imprimir paths, entrada o credencial.
        out = {"ok": False, "motivo": "entrada_o_config_invalida",
               "usar_principal": True, "permitir_movimientos": False,
               "requiere_simulacion": True}
    print(json.dumps(out, ensure_ascii=False, allow_nan=False))
    return 0 if out.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
