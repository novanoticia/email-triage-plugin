#!/usr/bin/env python3
"""Ollama local (`ollama serve`): el único evaluador en el que el correo no
sale del Mac.

Contrato comprobado en un Mac real el 2026-11-01 (`scripts/sonda_ollama.py`,
Ollama 0.40.13, MacBook Pro de 16 GB, un correo ficticio, dos ejecuciones):
- `ollama serve` expone `/v1/chat/completions` compatible con Chat
  Completions en `127.0.0.1:11434`, sin clave.
- `qwen3.5:latest` acepta `response_format` con `json_schema` estricto y su
  respuesta lo cumple; devuelve `model` igual al pedido y `usage`
  (4.144 tokens de entrada, 1.900-2.300 de salida).
- Con menos de 24 GB, Ollama usa 4.096 tokens de contexto y recortaría la
  petición: hay que arrancarlo con `OLLAMA_CONTEXT_LENGTH=16384 ollama serve`
  (`ollama ps` debe decir 16384). El plugin no puede comprobarlo antes.
- Tarda 105-119 s por correo: el tope de `timeout_segundos` es 600 aquí, no
  60. `stream: false` y `reasoning_effort: "none"` van siempre.
Sin coste por token. Nada sale del Mac, pero el doble consentimiento se exige
igual: el plugin no puede saber si `ollama serve` reenvía a otro sitio.
"""
import clasificadores as nc
from clasificadores import _exigir
from evaluadores import extraer_chat

PUERTO = 11434
ENDPOINT = nc.LOOPBACK + "%d/v1/chat/completions" % PUERTO
VARIABLE_CLAVE = None  # sin clave: el servidor local no la pide
MODELO_POR_DEFECTO = "qwen3.5:latest"
MODELOS = (MODELO_POR_DEFECTO,)  # solo los comprobados con la sonda
PRECIOS_MTOK = {MODELO_POR_DEFECTO: (0.0, 0.0)}  # sin facturación por token
TARIFA_FECHA = "2026-11-01"
TIMEOUT_MAXIMO = 600


def cuerpo(modelo, mensajes, esquema):
    return {"model": modelo, "messages": mensajes, "stream": False,
            "reasoning_effort": "none",
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
    return True


def solicitar(body, key, timeout):
    return nc.solicitar(ENDPOINT, body, None, timeout)
