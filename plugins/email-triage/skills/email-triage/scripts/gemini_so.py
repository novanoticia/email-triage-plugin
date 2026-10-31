#!/usr/bin/env python3
"""Gemini generateContent con JSON Schema. Consulta oficial: 2026-10-30.

https://ai.google.dev/gemini-api/docs/models/gemini-3.5-flash-lite
https://ai.google.dev/gemini-api/docs/generate-content/structured-output
https://ai.google.dev/gemini-api/docs/pricing
La ficha declara Structured outputs: Supported. El esquema se envía íntegro:
no traducir a responseSchema ni eliminar restricciones silenciosamente.
"""
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
    """Transporte común (`nc.solicitar`); la clave va en x-goog-api-key, nunca en la URL."""
    return nc.solicitar(ENDPOINT, body, key, timeout, cabecera_clave="x-goog-api-key")
