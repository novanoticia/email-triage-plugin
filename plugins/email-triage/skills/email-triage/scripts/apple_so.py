#!/usr/bin/env python3
"""Apple Foundation Models vía `fm serve` (macOS 27), en Private Cloud Compute.

Contrato comprobado en un Mac real el 2026-11-01 (sonda con un correo
ficticio), no en documentación pública:
- `fm serve --host 127.0.0.1 --port 8765` expone `/v1/chat/completions`
  compatible con Chat Completions, solo en loopback y sin clave.
- Modelos: `system` (on-device, 4.096 tokens de contexto en total) y `pcc`
  (Private Cloud Compute). Nuestra petición ocupa unos 4.090 tokens de
  entrada y la respuesta unos 1.400: no cabe en `system`, así que solo se
  admite `pcc`.
- Responde en streaming salvo `stream: false`. Acepta `response_format`
  con `json_schema` estricto y devuelve `model: "pcc"` y `usage`.
Con `pcc` los datos SALEN del Mac hacia Apple: requiere el mismo doble
consentimiento que los demás proveedores. `fm serve` debe estar abierto en
una Terminal en primer plano para que macOS permita PCC.
"""
import clasificadores as nc
from clasificadores import _exigir
from evaluadores import extraer_chat

PUERTO = 8765
ENDPOINT = nc.LOOPBACK + "%d/v1/chat/completions" % PUERTO
VARIABLE_CLAVE = None  # sin clave: el servicio local no la pide
MODELO_POR_DEFECTO = "pcc"
MODELOS = (MODELO_POR_DEFECTO,)
PRECIOS_MTOK = {MODELO_POR_DEFECTO: (0.0, 0.0)}  # sin facturación por token
TARIFA_FECHA = "2026-11-01"


def cuerpo(modelo, mensajes, esquema):
    return {"model": modelo, "messages": mensajes, "stream": False,
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
