#!/usr/bin/env python3
"""OpenAI Structured Outputs; contrato y precios consultados el 2026-10-30.

https://developers.openai.com/api/docs/models/gpt-6-luna
https://developers.openai.com/api/docs/guides/structured-outputs?api-mode=chat
https://developers.openai.com/api/docs/pricing
Chat Completions: una petición sin estado, sin herramientas ni historial;
permite reutilizar el sobre de Mistral. Responses no aporta nada necesario aquí.
"""
import re

import clasificadores as nc
from clasificadores import _exigir
from evaluadores import extraer_chat

ENDPOINT = "https://api.openai.com/v1/chat/completions"
VARIABLE_CLAVE = "OPENAI_API_KEY"
MODELO_POR_DEFECTO = "gpt-6-luna"
# Lista cerrada de modelos cuya ficha documenta Structured Outputs. Ampliarla
# requiere consultar su contrato y añadir pruebas; un nombre plausible no basta.
MODELOS = (MODELO_POR_DEFECTO,)
PRECIOS_MTOK = {MODELO_POR_DEFECTO: (0.10, 0.50)}  # USD: entrada, salida estándar
TARIFA_FECHA = "2026-10-30"


def cuerpo(modelo, mensajes, esquema):
    return {"model": modelo, "messages": mensajes,
            "response_format": {"type": "json_schema", "json_schema": {
                "name": "evaluacion_correo", "strict": True, "schema": esquema}},
            "store": False, "max_completion_tokens": 8192, "reasoning_effort": "none"}


def extraer(respuesta):
    return extraer_chat(respuesta)


def modelo_efectivo(respuesta, solicitado):
    # Chat Completions puede devolver el snapshot fechado del alias pedido
    # (`<modelo>-AAAA-MM-DD`); cualquier otro nombre es otro modelo.
    efectivo = respuesta.get("model")
    _exigir(isinstance(efectivo, str) and (
        efectivo == solicitado
        or re.fullmatch(re.escape(solicitado) + r"-[0-9]{4}-[0-9]{2}-[0-9]{2}", efectivo)),
        "modelo_inesperado")
    return efectivo


def uso(respuesta):
    return nc.uso_tokens(respuesta.get("usage"), ("prompt_tokens", "completion_tokens"))


def coste_conocido(respuesta):
    # No extrapolar tarifa simple a caché, escrituras o niveles distintos.
    detalles = respuesta.get("usage", {}).get("prompt_tokens_details", {})
    return (isinstance(detalles, dict)
            and all(type(detalles.get(k, 0)) is int and detalles.get(k, 0) == 0
                    for k in ("cached_tokens", "cache_write_tokens"))
            and respuesta.get("service_tier", "default") == "default")


def solicitar(body, key, timeout):
    return nc.solicitar(ENDPOINT, body, key, timeout)
