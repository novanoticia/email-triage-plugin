#!/usr/bin/env python3
"""Mistral Structured Outputs; documentación consultada el 2026-10-30.

https://docs.mistral.ai/models/ministral-3-3b-25-12
https://docs.mistral.ai/studio/conversations/structured-output/custom
https://docs.mistral.ai/inference/pricing
El proveedor antepone el esquema al sistema: no lo duplicamos en el prompt.
"""
import clasificadores as nc
from clasificadores import _exigir
from evaluadores import extraer_chat

ENDPOINT = "https://api.mistral.ai/v1/chat/completions"
VARIABLE_CLAVE = "MISTRAL_API_KEY"
MODELO_POR_DEFECTO = "ministral-3b-2512"
MODELOS = (MODELO_POR_DEFECTO,)
PRECIOS_MTOK = {MODELO_POR_DEFECTO: (0.10, 0.10)}  # USD: entrada y salida estándar
TARIFA_FECHA = "2026-10-30"


def cuerpo(modelo, mensajes, esquema):
    return {"model": modelo, "messages": mensajes, "max_tokens": 8192,
            "response_format": {"type": "json_schema", "json_schema": {
                "name": "evaluacion_correo", "strict": True, "schema": esquema}}}


def extraer(respuesta):
    return extraer_chat(respuesta)


def modelo_efectivo(respuesta, solicitado):
    _exigir(respuesta.get("model") == solicitado, "modelo_inesperado")
    return solicitado


def uso(respuesta):
    return nc.uso_tokens(respuesta.get("usage"), ("prompt_tokens", "completion_tokens"))


def coste_conocido(respuesta):
    # Estimación a tarifa sin descuento; no se pide caché explícita ni prioridad.
    return True


def solicitar(body, key, timeout):
    return nc.solicitar(ENDPOINT, body, key, timeout)
