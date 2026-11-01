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
  (`ollama ps` debe decir 16384). Desde v3.26.1 `preflight` lo comprueba
  antes del primer correo con `GET /api/ps` (ver más abajo).
- Tarda 105-119 s por correo: el tope de `timeout_segundos` es 600 aquí, no
  60. `stream: false` y `reasoning_effort: "none"` van siempre.
Sin coste por token. Nada sale del Mac, pero el doble consentimiento se exige
igual: el plugin no puede saber si `ollama serve` reenvía a otro sitio.
"""
import math

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
PS = nc.LOOPBACK + "%d/api/ps" % PUERTO
TIMEOUT_PS = 10  # `/api/ps` no genera: responde al momento o no responde
# Contexto necesario = entrada estimada + margen de salida, calculado por
# petición (v3.26.1). Medido con la sonda del 2026-11-01: 16.699 caracteres
# de mensajes = 4.144 tokens de entrada (4,03 car./token; el esquema no
# cuenta: Ollama lo aplica como gramática, no en el prompt). Se estima con 3
# car./token para sobrestimar, nunca quedarse corto. La salida observada fue
# de 1.900-2.300 tokens; el margen es 1,5 veces el máximo.
CARACTERES_POR_TOKEN = 3
SALIDA_MAXIMA_OBSERVADA = 2300
MARGEN_SALIDA = math.ceil(SALIDA_MAXIMA_OBSERVADA * 1.5)
# v3.26.2 (medición real del 2026-11-01, contexto 16.384 comprobado con
# `ollama ps`): sin tope, el correo 2 generó más de 300 s, el lote se detuvo
# y Ollama siguió generando la respuesta abandonada, así que la ejecución
# siguiente falló en el correo 1. `max_tokens` = el margen que reserva el
# preflight: la salida nunca supera lo que se comprobó que cabe, y a ~18
# tokens/s acaba en unos 190 s, por debajo de los 300 recomendados. Una
# respuesta cortada sale `respuesta_incompleta` y solo descarta su correo.
MAX_SALIDA = MARGEN_SALIDA


def cuerpo(modelo, mensajes, esquema):
    return {"model": modelo, "messages": mensajes, "stream": False,
            "reasoning_effort": "none", "max_tokens": MAX_SALIDA,
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


def contexto_necesario(body):
    """Tokens que necesita una petición: mensajes estimados + margen de salida."""
    caracteres = sum(len(m.get("content", "")) for m in body["messages"])
    return math.ceil(caracteres / CARACTERES_POR_TOKEN) + MARGEN_SALIDA


def preflight(modelo, bodies, timeout, consultar=None):
    """Antes del primer correo: ¿el modelo cargado tiene contexto suficiente?

    Solo lectura GET de `/api/ps` en loopback, por la misma guarda que el
    envío (`nc.solicitar`: solo `http://127.0.0.1:`, sin proxy, sin
    redirecciones). `/api/show` no sirve: da el máximo entrenado del modelo y
    los parámetros del Modelfile, no el contexto con el que el servidor lo
    cargó (`OLLAMA_CONTEXT_LENGTH`). Por eso el modelo tiene que estar ya
    cargado; si no lo está, `modelo_no_cargado` (la primera petición lo
    cargaría con un contexto que nadie ha comprobado). La API no expone si
    un modelo está generando: un servidor ocupado no se detecta aquí.
    Devuelve el detalle para la salida o lanza `ErrorClasificador`.
    """
    consultar = consultar or (lambda: nc.solicitar(PS, None, None, min(timeout, TIMEOUT_PS)))
    necesario = max(contexto_necesario(b) for b in bodies)
    respuesta = consultar()
    modelos = respuesta.get("models") if isinstance(respuesta, dict) else None
    _exigir(isinstance(modelos, list), "respuesta_ps_invalida")
    cargado = [m for m in modelos if isinstance(m, dict)
               and modelo in (m.get("name"), m.get("model"))]
    detalle = {"contexto_necesario": necesario}
    _exigir(bool(cargado), "modelo_no_cargado", detalle)
    contexto = cargado[0].get("context_length")
    _exigir(type(contexto) is int and contexto > 0, "contexto_no_verificable", detalle)
    detalle["contexto_servidor"] = contexto
    _exigir(contexto >= necesario, "contexto_insuficiente", detalle)
    return detalle
