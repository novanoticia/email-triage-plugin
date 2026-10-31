#!/usr/bin/env python3
"""Gemini generateContent con JSON Schema. Consulta oficial: 2026-10-30.

https://ai.google.dev/gemini-api/docs/models/gemini-3.5-flash-lite
https://ai.google.dev/gemini-api/docs/generate-content/structured-output
https://ai.google.dev/gemini-api/docs/pricing
La ficha declara Structured outputs: Supported. El esquema se envía íntegro:
no traducir a responseSchema ni eliminar restricciones silenciosamente.
"""
import http.client
import urllib.error
import urllib.request

import clasificadores as nc
from clasificadores import _exigir

MODELO_POR_DEFECTO = "gemini-3.5-flash-lite"
MODELOS = (MODELO_POR_DEFECTO,)
ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/models/" + MODELO_POR_DEFECTO + ":generateContent"
VARIABLE_CLAVE = "GEMINI_API_KEY"
PRECIOS_MTOK = {MODELO_POR_DEFECTO: (0.30, 2.50)}  # USD: entrada, salida (incluye pensamiento)
TARIFA_FECHA = "2026-10-30"


def cuerpo(modelo, mensajes, esquema):
    _exigir(modelo in MODELOS, "modelo_no_verificado")
    return {"systemInstruction": {"parts": [{"text": mensajes[0]["content"]}]},
            "contents": [{"role": "user", "parts": [{"text": mensajes[1]["content"]}]}],
            "generationConfig": {"responseFormat": {"text": {
                "mimeType": "APPLICATION_JSON", "schema": esquema}}, "maxOutputTokens": 8192}}


def extraer(respuesta):
    feedback = respuesta.get("promptFeedback", {})
    _exigir(isinstance(feedback, dict), "respuesta_proveedor_invalida")
    _exigir(not feedback.get("blockReason"), "proveedor_rehusa")
    candidatos = respuesta.get("candidates")
    _exigir(bool(candidatos), "proveedor_rehusa")
    _exigir(isinstance(candidatos, list) and len(candidatos) == 1
            and isinstance(candidatos[0], dict), "respuesta_proveedor_invalida")
    c = candidatos[0]
    _exigir(c.get("finishReason") not in ("SAFETY", "RECITATION", "BLOCKLIST",
            "PROHIBITED_CONTENT", "SPII", "IMAGE_SAFETY"), "proveedor_rehusa")
    _exigir(c.get("finishReason") == "STOP", "respuesta_incompleta")
    contenido = c.get("content", {})
    _exigir(isinstance(contenido, dict), "respuesta_proveedor_invalida")
    partes = contenido.get("parts", [])
    _exigir(isinstance(partes, list), "respuesta_proveedor_invalida")
    textos = []
    for parte in partes:
        _exigir(isinstance(parte, dict) and isinstance(parte.get("text"), str)
                and not set(parte) - {"text", "thought", "thoughtSignature"}, "respuesta_proveedor_invalida")
        _exigir(type(parte.get("thought", False)) is bool, "respuesta_proveedor_invalida")
        if not parte.get("thought", False):
            textos.append(parte["text"])
    texto = "".join(textos)
    _exigir(bool(texto.strip()), "proveedor_rehusa")
    return nc._cargar_json(texto)


def modelo_efectivo(respuesta, solicitado):
    _exigir(respuesta.get("modelVersion") == solicitado, "modelo_inesperado")
    return solicitado


def uso(respuesta):
    u = respuesta.get("usageMetadata")
    par = nc.uso_tokens(u, ("promptTokenCount", "candidatesTokenCount"))
    if par is None:
        return None
    pensamiento = u.get("thoughtsTokenCount", 0)
    if type(pensamiento) is not int or not 0 <= pensamiento <= 1_000_000_000:
        return None
    return par[0], par[1] + pensamiento


def coste_conocido(respuesta):
    # Tarifa estándar de pago sin descuento de caché ni tramo gratuito.
    return True


def solicitar(body, key, timeout):
    """Defensas de nc.solicitar; única diferencia: x-goog-api-key, nunca URL."""
    req = urllib.request.Request(ENDPOINT, data=nc._json(body), method="POST", headers={
        "x-goog-api-key": key, "Content-Type": "application/json", "Accept": "application/json"})
    try:
        with urllib.request.build_opener(nc._SinRedireccion()).open(req, timeout=timeout) as resp:
            _exigir(resp.status == 200 and resp.geturl() == ENDPOINT, "respuesta_http_inesperada")
            raw = resp.read(nc.MAX_JSON + 1)
            _exigir(len(raw) <= nc.MAX_JSON, "respuesta_excesiva")
            return nc._cargar_json(raw.decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raise nc.ErrorClasificador("http_%d" % exc.code) from None
    except (urllib.error.URLError, OSError, TimeoutError, http.client.HTTPException):
        raise nc.ErrorClasificador("fallo_red_o_timeout") from None
    except (ValueError, UnicodeError, RecursionError):
        raise nc.ErrorClasificador("respuesta_json_invalida") from None
